#!/usr/bin/env bash
# Download the public benchmark data we run against. Everything lands in data/, which is
# gitignored: these are other people's datasets, and they are large.
#
#   benchmarks/fetch.sh oracle   LongMemEval oracle — evidence sessions only, 15 MB (start here)
#   benchmarks/fetch.sh s        LongMemEval_S — ~40 sessions per question, 277 MB
#   benchmarks/fetch.sh m        LongMemEval_M — ~500 sessions per question, 2.7 GB
#   benchmarks/fetch.sh mab      MemoryAgentBench — four competencies, parquet
set -euo pipefail
cd "$(dirname "$0")/.."
LME=https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main
MAB=https://huggingface.co/datasets/ai-hyz/MemoryAgentBench/resolve/main

get() {  # get <url> <path>
    if [ -s "$2" ]; then echo "have $2"; return; fi
    mkdir -p "$(dirname "$2")"
    echo "fetching $2"
    curl -fL --progress-bar -o "$2" "$1"
}

for what in "$@"; do
    case "$what" in
        oracle) get "$LME/longmemeval_oracle.json" data/longmemeval/longmemeval_oracle.json ;;
        s) get "$LME/longmemeval_s_cleaned.json" data/longmemeval/longmemeval_s.json ;;
        m) get "$LME/longmemeval_m_cleaned.json" data/longmemeval/longmemeval_m.json ;;
        mab)
            for part in Accurate_Retrieval Conflict_Resolution Long_Range_Understanding Test_Time_Learning; do
                get "$MAB/data/${part}-00000-of-00001.parquet" "data/memoryagentbench/${part}.parquet"
            done ;;
        *) echo "unknown: $what (oracle|s|m|mab)"; exit 2 ;;
    esac
done
