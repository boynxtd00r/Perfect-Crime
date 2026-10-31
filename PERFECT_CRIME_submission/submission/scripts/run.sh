#!/bin/bash
# usage: run.sh <result_dir> <name> <args...>   -> сохраняет JSON и код завершения
d=$1; n=$2; shift 2
python3 -m perfectcrime "$@" > "results/$d/$n.json" 2> "results/$d/$n.stderr.txt"
code=$?
echo "$code" > "results/$d/$n.exit.txt"
echo "$ $n: python3 -m perfectcrime $*"; echo "exit=$code"; python3 -c "import json,sys;print(json.dumps(json.load(open(sys.argv[1])),ensure_ascii=False))" "results/$d/$n.json"
