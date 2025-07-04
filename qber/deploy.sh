#!/bin/bash

Alice='KAlice2'
Bob='KBob2'

rsync -v target/release/alice $Alice:~/qline/bin/qber
rsync -v target/release/bob $Bob:~/qline/server/qber






