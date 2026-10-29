#!/bin/bash
# usage: compare.sh <tag> [full|legs ...] -> .captures/T011/v7/compare_<set>_<tag>.png (reference left, model right)
set -e
cd /home/archwayzero/game
T=reference/hero/turnaround; R=.captures/T011/v7/r; O=.captures/T011/v7; tag=$1; shift
sets=${@:-full legs}
F=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
L="fontfile=$F:fontsize=18:fontcolor=white:x=6:y=6:box=1:boxcolor=black@0.6:boxborderw=2"
for s in $sets; do
  if [ $s = full ]; then CW=300; CX=282; else CW=432; CX=216; fi
  IN=""; FG=""; i=0
  for a in 000 045 090 135 180 225 270 315; do
    IN="$IN -i $T/${s}_$a.png -i $R/${tag}_${s}_$a.png"
    FG="$FG[$i]crop=$CW:480:$CX:0,drawtext=$L:text='ref $a'[a$i];[$((i+1))]crop=$CW:480:$CX:0,drawtext=$L:text='model $a'[b$i];[a$i][b$i]hstack=2,pad=iw+6:ih:0:0:white[p$((i/2))];"
    i=$((i+2))
  done
  FG="$FG[p0][p1][p2][p3]hstack=4[top];[p4][p5][p6][p7]hstack=4[bot];[top][bot]vstack=2"
  python3 tools/qa/memguard.py --expect-peak-mb 500 -- ffmpeg -loglevel error -y $IN -filter_complex "$FG" $O/compare_${s}_${tag}.png
done
