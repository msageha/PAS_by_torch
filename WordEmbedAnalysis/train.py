import argparse
from allennlp.modules import elmo
from collections import defaultdict
import numpy as np
import torch.optim as optim
from pprint import pprint
import torch
import torch.nn as nn
from tqdm import tqdm

import test
from model import BiLSTM

import sys
sys.path.append('../utils')
from loader import DatasetLoading, load_model
from store import save_model, dump_dict


# init model
def weights_init(m):
    classname = m.__class__.__name__
    if hasattr(m, 'weight') and (classname.find('Embedding') == -1):
        nn.init.xavier_uniform_(m.weight.data, gain=nn.init.calculate_gain('relu'))


def create_arg_parser():
    parser = argparse.ArgumentParser(description='main function parser')
    parser.add_argument('--type', dest='dataset_type', required=True, choices=['intra', 'inter'], help='dataset: "intra" or "inter"')
    parser.add_argument('--epochs', '-e', dest='max_epoch', type=int, default=15, help='max epoch')
    parser.add_argument('--emb_type', dest='emb_type', required=True, choices=['Word2Vec', 'Word2VecWiki', 'FastText', 'ELMo', 'Random', 'ELMoForManyLangs', 'None'], help='word embedding type')
    parser.add_argument('--emb_path', dest='emb_path', help='word embedding path')
    parser.add_argument('--emb_requires_grad_false', dest='emb_requires_grad', action='store_false', help='fixed word embedding or not')
    parser.add_argument('--emb_dim', type=int, default=200, help='word embedding dimension')
    parser.add_argument('--gpu', '-g', dest='gpu', type=int, default=-1, help='GPU ID for execution')
    parser.add_argument('--batch', '-b', dest='batch_size', type=int, default=16, help='mini batch size')
    parser.add_argument('--case', '-c', dest='case', type=str, required=True, choices=['ga', 'o', 'ni'], help='target "case" type')
    parser.add_argument('--media', '-m', dest='media', nargs='+', type=str, default=['OC', 'OY', 'OW', 'PB', 'PM', 'PN'], choices=['OC', 'OY', 'OW', 'PB', 'PM', 'PN'], help='training media type')
    parser.add_argument('--dump_dir', dest='dump_dir', type=str, required=True, help='model dump directory path')
    parser.add_argument('--exo1_word', dest='exo1_word', type=str, default='', help='exo1 initialize word')
    parser.add_argument('--exo2_word', dest='exo2_word', type=str, default='', help='exo2 initialize word')
    parser.add_argument('--exoX_word', dest='exoX_word', type=str, default='', help='exoX initialize word')
    return parser


def initialize_model(gpu, vocab_size, v_vec, emb_requires_grad, args):
    emb_dim = args.emb_dim
    h_dim = None
    class_num = 2
    is_gpu = True
    if gpu == -1:
        is_gpu = False
    if args.emb_type == 'ELMo' or args.emb_type == 'ELMoForManyLangs':
        bilstm = BiLSTM(emb_dim, h_dim, class_num, vocab_size, is_gpu, v_vec, emb_type=args.emb_type, elmo_model_dir=args.emb_path)
    elif args.emb_type == 'None':
        bilstm = BiLSTM(emb_dim, h_dim, class_num, vocab_size, is_gpu, v_vec, emb_type=args.emb_type)
    else:
        bilstm = BiLSTM(emb_dim, h_dim, class_num, vocab_size, is_gpu, v_vec, emb_type=args.emb_type)
    if is_gpu:
        bilstm = bilstm.cuda()

    for m in bilstm.modules():
        print(m.__class__.__name__)
        weights_init(m)

    if args.emb_type != 'ELMo' and args.emb_type != 'ELMoForManyLangs' and args.emb_type != 'None':
        for param in bilstm.word_embed.parameters():
            param.requires_grad = emb_requires_grad

    return bilstm


def translate_df_tensor(df_list, keys, gpu_id):
    vec = [np.array(i[keys], dtype=np.int) for i in df_list]
    vec = np.array(vec)
    vec = [torch.tensor(i) for i in vec]
    vec = nn.utils.rnn.pad_sequence(vec, batch_first=True, padding_value=0)
    if gpu_id >= 0:
        vec = vec.cuda()
    return vec


def translate_df_y(df_list, keys, gpu_id):
    vec = [int(i[keys].split(',')[0]) for i in df_list]
    vec = torch.tensor(vec)
    if gpu_id >= 0:
        vec = vec.cuda()
    return vec


def translate_batch(batch, gpu, case, emb_type):
    x = batch[:, 0]
    y = batch[:, 1]
    files = batch[:, 2]
    batchsize = len(batch)

    max_length = x[0].shape[0]
    sentences = [i['単語'].values[4:] for i in batch[:, 0]]
    sentences = np.array(sentences)
    if emb_type == 'ELMo':
        x_wordID = elmo.batch_to_ids(sentences)
        if gpu >= 0:
            x_wordID = x_wordID.cuda()
    elif emb_type == 'ELMoForManyLangs':
        x_wordID = sentences
    else:
        x_wordID = translate_df_tensor(x, ['単語ID'], gpu)
        x_wordID = x_wordID.reshape(batchsize, -1)
    x_feature_emb_list = []
    for i in range(6):
        x_feature_emb = translate_df_tensor(x, [f'形態素{i}'], gpu)
        x_feature_emb = x_feature_emb.reshape(batchsize, -1)
        x_feature_emb_list.append(x_feature_emb)
    x_feature = translate_df_tensor(x, ['n単語目', 'n文節目', 'is主辞', 'is機能語', 'is_target_verb', '述語からの距離'], gpu)
    x = [x_wordID, x_feature_emb_list, x_feature]

    y = translate_df_y(y, case, -1)
    y = y.reshape(batchsize)
    y = torch.eye(max_length, dtype=torch.long)[y]
    if gpu >= 0:
        y = y.cuda()

    return x, y, files


def run(trains, vals, bilstm, args):
    print('--- start training ---')
    epochs = args.max_epoch + 1
    lr = 0.001  # 学習係数
    results = {}
    optimizer = optim.Adam(bilstm.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()
    for epoch in range(1, epochs):
        N = len(trains)
        perm = np.random.permutation(N)
        running_loss = 0.0
        running_correct = 0
        running_samples = 0
        bilstm.train()
        for i in tqdm(range(0, N, args.batch_size)):
            bilstm.zero_grad()
            optimizer.zero_grad()
            batch = trains[perm[i:i + args.batch_size]]
            # 0 paddingするために，長さで降順にソートする．
            argsort_index = np.array([i.shape[0] for i in batch[:, 0]]).argsort()[::-1]
            batch = batch[argsort_index]
            x, y, _ = translate_batch(batch, args.gpu, args.case, args.emb_type)
            batchsize = len(batch)
            out = bilstm.forward(x)
            out = torch.cat((out[:, :, 0].reshape(batchsize, 1, -1), out[:, :, 1].reshape(batchsize, 1, -1)), dim=1)
            pred = out.argmax(dim=2)[:, 1]
            running_correct += pred.eq(y.argmax(dim=1)).sum().item()
            running_samples += len(batch)
            loss = criterion(out, y)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()

        print(f'[epoch: {epoch}]\tloss: {running_loss/(running_samples/args.batch_size)}\tacc(one_label): {running_correct/running_samples}')
        _results, _ = test.run(vals, bilstm, args)
        results[epoch] = _results
        save_model(epoch, bilstm, args.dump_dir, args.gpu)
    dump_dict(results, args.dump_dir, 'training_logs')
    best_epochs = defaultdict(lambda: defaultdict(float))
    for epoch in results:
        for domain in sorted(results[epoch].keys()):
            if results[epoch][domain]['F1']['F1-score']['total'] > best_epochs[domain]['F1-score(total)']:
                best_epochs[domain]['F1-score(total)'] = results[epoch][domain]['F1']['F1-score']['total']
                best_epochs[domain]['acc(one_label)'] = results[epoch][domain]['acc(one_label)']
                best_epochs[domain]['epoch'] = epoch
    dump_dict(best_epochs, args.dump_dir, 'training_result')
    print('--- finish training ---\n--- best F1-score epoch for each domain ---')
    for domain in sorted(best_epochs.keys()):
        print(f'{domain} [epoch: {best_epochs[domain]["epoch"]}]\tF1-score: {best_epochs[domain]["F1-score(total)"]}\tacc(one_label): {best_epochs[domain]["acc(one_label)"]}')


def main():
    parser = create_arg_parser()
    args = parser.parse_args()

    dl = DatasetLoading(args.emb_type, args.emb_path, media=args.media, exo1_word=args.exo1_word, exo2_word=args.exo2_word, exoX_word=args.exoX_word)
    if args.dataset_type == 'intra':
        dl.making_intra_df()
    elif args.dataset_type == 'inter':
        dl.making_inter_df()
    else:
        raise ValueError()

    trains, vals, tests = dl.split(args.dataset_type)
    args.__dict__['trains_size'] = len(trains)
    args.__dict__['vals_size'] = len(vals)
    args.__dict__['tests_size'] = len(tests)

    bilstm = initialize_model(args.gpu, vocab_size=len(dl.wv.index2word), v_vec=dl.wv.vectors, emb_requires_grad=args.emb_requires_grad, args=args)
    dump_dict(args.__dict__, args.dump_dir, 'args')
    pprint(args.__dict__)
    run(trains, vals, bilstm, args)
    # train_loader = data.DataLoader(trains, batch_size=16, shuffle=True)
    # vals_loader = data.DataLoader(vals, batch_size=16, shuffle=True)

if __name__ == '__main__':
    main()
