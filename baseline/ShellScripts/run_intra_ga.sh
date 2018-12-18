#$ -cwd
#$ -l q_node=1
# 実行時間を指定（5分）
#$ -l h_rt=24:00:00
# 名前（hill_climbing.e[ジョブ番号？]，hill_climbing.o[ジョブ番号？]というそれぞれエラー出力，標準出力ファイルが生成される．ただしこれの内容は信用できない）
#$ -N PAS_intra_ga_Fix
# Module コマンドの初期化
. /etc/profile.d/modules.sh
module load cuda/9.0.176 cudnn/7.1 gnuplot
# 自分のAnacondaとかjumanとか読ませるため
source /home/2/17M30683/.bash_profile
cd /gs/hs0/tga-cl/sango-m-ab/research2/PAS_by_torch/baseline/
# python3 train.py --type "intra" --epochs 10 --emb_type Random --emb_path "train_words.txt" --gpu 0 --case "ga" --dump_dir "intra/Random_Fix/ga" --emb_requires_grad_false
python3 train.py --type "intra" --epochs 10 --emb_type Word2Vec --emb_path "../../data/embedding/Word2Vec/OC.bin" --gpu 0 --case "ga" --dump_dir "intra/Word2Vec/OC/ga" --emb_requires_grad_false
python3 train.py --type "intra" --epochs 10 --emb_type Word2Vec --emb_path "../../data/embedding/Word2Vec/OY.bin" --gpu 0 --case "ga" --dump_dir "intra/Word2Vec/OY/ga" --emb_requires_grad_false
python3 train.py --type "intra" --epochs 10 --emb_type Word2Vec --emb_path "../../data/embedding/Word2Vec/OW.bin" --gpu 0 --case "ga" --dump_dir "intra/Word2Vec/OW/ga" --emb_requires_grad_false
python3 train.py --type "intra" --epochs 10 --emb_type Word2Vec --emb_path "../../data/embedding/Word2Vec/PB.bin" --gpu 0 --case "ga" --dump_dir "intra/Word2Vec/PB/ga" --emb_requires_grad_false
python3 train.py --type "intra" --epochs 10 --emb_type Word2Vec --emb_path "../../data/embedding/Word2Vec/PM.bin" --gpu 0 --case "ga" --dump_dir "intra/Word2Vec/PM/ga" --emb_requires_grad_false
python3 train.py --type "intra" --epochs 10 --emb_type Word2Vec --emb_path "../../data/embedding/Word2Vec/PN.bin" --gpu 0 --case "ga" --dump_dir "intra/Word2Vec/PN/ga" --emb_requires_grad_false
# python3 train.py --type "intra" --epochs 10 --emb_type FastText --emb_path "../../data/embedding/FastText/All.bin" --gpu 0 --case "ga" --dump_dir "intra/FastText_Fix/All/ga" --emb_requires_grad_false
# python3 test.py --gpu 0 --load_dir "intra/FastText/All/ga"
# python3 test.py --gpu 0 --load_dir "intra/FastText_Fix/All/ga"
# python3 test.py --gpu 0 --load_dir "intra/FastText/All/o"
# python3 test.py --gpu 0 --load_dir "intra/FastText_Fix/All/o"
# python3 test.py --gpu 0 --load_dir "intra/FastText/All/ni"
# python3 test.py --gpu 0 --load_dir "intra/FastText_Fix/All/ni"