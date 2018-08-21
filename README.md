# fast5_fetcher
Doing the heavy lifting for you.

<p align="center"><img src="images/fetch.png" alt="fast5_fetcher" width="50%" height="50%"></p>

Fast5 Fetcher is a tool for fetching fast5 files after filtering via demultiplexing, alignment, or other, to improve downstream processing efficiency of nanopore sequencing data.

It takes 3 files as input: fastq/paf/flat, sequencing_summary, index

The fastq/paf/flat files are what you want to extract.
The sequencing summary file is from guppy or albacore, or both. It doesn't really matter.
(Try to exclude the headers when you merge files if you run albacore like we do in array jobs)
The index file is a list of all files from tarballs of fast5 files. Using full paths helps
make it all work on an HPC environtment.

This should be pretty straight forward to use for those who regularly use SGE.
Any questions, issues, or requested features, feel free to shoot me a message on any number
of social media platforms. Happy to help :)

I keep finding more and more uses for this tool across multiple projects. I hope you find it helpful, and would love to know if you use it in your work.

## Instructions for use:
quick initial guide for use. I'll expand to demonstrate all usage methods, as well as some timing data at a later date.

##### To make index files:

This is assuming you have a collection of .tar files containing fast5 files.
It will still work if there are other files in the tar ball, as long as it doesn't contain
other .tar files.

```bash
for file in $(pwd)/fast5/*fast5.tar; do echo $file; tar -tf $file; done >> name.index
```
then cat them all together and gzip.

```bash
for file in ./*.index; do cat $file; done >> ../all.name.index

gzip all.name.index
```
##### To make the seq_sum.txt.gz
To cat together multiple seq_sum.txt.gz files - preferably all in the same dir.

This creates the first header:
```bash
zcat $(ls sequencing_summary* | head -1) | head -1 > ../seq_sum.txt
```
This appends all the lines but skips the header.
```bash
for file in logs/sequencing_summary*; do zcat $file | tail -n +2; done >> ../seq_sum.txt &
```
Then gzip it to save some space.
```bash
gzip seq_sum.txt
```

Inputs can be gzipped or not. I'd recommend gzipping to save that precious hpc quota.


## fast5_fetcher.py

##### Full usage:
```
usage: fast5_fetcher.py [-h] [-q FASTQ | -f PAF | -r READS] [-b FAST5]
                        [-s SEQ_SUM] [-i INDEX] [-o OUTPUT] [-p PROCS] [-z]

fast_puller - extraction of specific fast5 files

optional arguments:
  -h, --help            show this help message and exit
  -q FASTQ, --fastq FASTQ
                        fastq.gz with cell reads
  -f PAF, --paf PAF     paf alignment file for reads
  -r READS, --reads READS
                        flat file of read ids
  -b FAST5, --fast5 FAST5
                        fast5.tar path to extract from
  -s SEQ_SUM, --seq_sum SEQ_SUM
                        sequencing_summary.txt.gz file
  -i INDEX, --index INDEX
                        index.gz file mapping fast5 files in tar archives
  -o OUTPUT, --output OUTPUT
                        output directory for extracted fast5s
  -p PROCS, --procs PROCS
                        Number of CPUs to use - TODO: NOT YET IMPLEMENTED
  -z, --pppp            Print out tar commands in batches for further
                        processing
```


##### To run:
```bash
python fast5_fetcher.py -q test.fastq.gz -s seq_sum.txt.gz -i all.name.index.gz -o ./fast5
```


Fast5 Fetcher was built to work on Sun Grid Engine, exploiting the heck out of array jobs.
Here is a quick example using a flat file as an example

Create the SGE file (and associated directories)
Note the use of ${SGE_TASK_ID} to use the array job as the pointer to a particular file

##### fetch.sge
```bash
source ~/work/venv2714/bin/activate
mkdir ${TMPDIR}/fast5

time python fast5_fetcher.py -r ./cells.${SGE_TASK_ID}.readIDs.txt -s RNA_seq_sum.txt.gz -i cells.index.gz -o ${TMPDIR}/fast5/

tar -cf ${TMPDIR}/cells.${SGE_TASK_ID}.tar --transform='s/.*\///' ${TMPDIR}/fast5/*.fast5
cp ${TMPDIR}/cells.${SGE_TASK_ID}.tar ./cells/fast5
```

##### Create CMD and launch

```bash
CMD="qsub -cwd -V -pe smp 1 -N F5F -S /bin/bash -t 1-10433 -tc 80 -l mem_requested=20G,h_vmem=20G,tmp_requested=20G ./fetch.sge"

echo $CMD && $CMD
```


## batch_tater.py

Potato scripting engaged

This little script is for use with the -z option of fast5_fetcher.py.
It is used to extract only the files you need from a single tarball, of course, abusing array jobs.

A recent test on ~1.4Tb of data, accross ~16/20 million files took about 10min (1CPU) to extract and organise the file lists with fast5_fetch.py, and about 2min to to extract and repackage with batch_tater.py.

This is best used when you want to do something all at once and filter your reads. other approaches may be better when you are demultiplexing.




