# fast5_fetcher

#### Doing the heavy lifting for you.

<p align="left"><img src="images/fetch.jpg" alt="fast5_fetcher" width="30%" height="30%"></p>

**fast5_fetcher** is a tool for fetching nanopore fast5 files to save time and simplify downstream analysis.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.1413903.svg)](https://doi.org/10.5281/zenodo.1413903)

## Contents

# Background

Reducing the number of fast5 files per folder in a single experiment was a welcomed addition to MinKnow. However this also made it rather useful for manual basecalling on a cluster, using array jobs, where each folder is basecalled individually, producing its own `sequencing_summary.txt`, `reads.fastq`, and reads folder containing the newly basecalled fast5s. Taring those fast5 files up into a single file was needed to keep the sys admins at bay, complaining about our millions of individual files on their drives. This meant, whenever there was a need to use the fast5 files from an experiment, or many experiments, unpacking the fast5 files was a significant hurdle both in time and disk space.

**fast5_fetcher** was built to  address this bottleneck. By building an index file of the tarballs, and using the `sequencing_summary.txt` file to match readIDs with fast5 filenames, only the fast5 files you need can be  extracted, either temporarily in a pipeline, or permanently, reducing space and simplifying downstream work flows.

# Requirements

Following a self imposed guideline, most things written to handle nanopore data or bioinformatics in general, will use as little 3rd party libraries as possible, aiming for only core libraries, or have all included files in the package.

In the case of `fast5_fetcher.py` and `batch_tater.py`, only core python libraries are used. So as long as **Python 2.7+** is present, everything should work with no extra steps. (Python 3 compatibility is coming in the next big update)

##### Operating system:

There is one catch. Everything is written primarily for use with **Linux**. Due to **MacOS** running on Unix, so long as the GNU tools are installed (see below), there should be minimal issues running it. **Windows 10** however may require more massaging to work with the new Linux integration.

# Getting Started

Building an index of fast5 files and their paths, as well as a simple bash script to control the workflow, be it on a local machine, or HPC, will depend on the starting file structure.

## File structures

The file structure is not overly important, however it will modify some of the commands used in the examples. I have endeavoured to include a few diverse uses, starting from different file states, but of course, I can't think of everything, so if there is something you wish to accomplished with `fast5_fetcher.py`, but can't quite get it to work for you, let me know, and perhaps I can make it easier for you.

#### 1. Raw structure (not preferred)

This is the most basic structure, where all files are present in an accessible state.

    ├── huntsman.fastq
    ├── sequencing_summary.txt       
    ├── huntsman_reads/              # Read folder
    │   ├── 0/                       # individual folders containing ~4000 fast5s
    |   |   ├── huntsman_read1.fast5
    |   |   └── huntsman_read2.fast5
    |   |   └── ...
    |   ├── 1/
    |   |   ├── huntsman_read#.fast5
    |   |   └── ...
    └── ├── ...

#### 2. Local basecalled structure

This structure is the typical structure post local basecalling
fastq and sequencing_summary files have been gzipped and the folders in the reads folder have been tarballed into one large file

    ├── huntsman.fastq.gz            # gzipped
    ├── sequencing_summary.txt.gz    # gzipped
    ├── huntsman_reads.tar           # Tarballed read folder
        |                            # Tarball expanded
        |-->│   ├── 0/               # individual folders inside tarball
            |   |   ├── huntsman_read1.fast5
            |   |   └── huntsman_read2.fast5
            |   |   └── ...
            |   ├── 1/
            |   |   ├── huntsman_read#.fast5
            |   |   └── ...
            └── ├── ...

#### 3. Parallel basecalled structure

This structure is post massively parallel basecalling, and looks like multiples of the above structure.

    ├── fastq/
    |   ├── huntsman.1.fastq.gz
    |   └── huntsman.2.fastq.gz
    |   └── huntsman.3.fastq.gz
    |   └── ...
    ├── logs/
    |    ├── sequencing_summary.1.txt.gz
    |    └── sequencing_summary.2.txt.gz
    |    └── sequencing_summary.3.txt.gz
    |    └── ...
    ├── fast5/
    |    ├── 1.tar
    |    └── 2.tar
    |    └── 3.tar
    |    └── ...

With this structure, combining the `.fastq` and `sequencing_summary.txt.gz` files is needed.

##### Combine fastq.gz files

```bash
for file in fastq/*.fastq.gz; do cat $file; done >> huntsman.fastq.gz
```

##### Combine sequencing_summary.txt.gz files

```bash
# create header
zcat $(ls logs/sequencing_summary*.txt.gz | head -1) | head -1 > sequencing_summary.txt

# combine all files, skipping first line header
for file in logs/sequencing_summary*.txt.gz; do zcat $file | tail -n +2; done >> sequencing_summary.txt

gzip sequencing_summary.txt
```

You should then have something like this:

    ├── huntsman.fastq.gz            # gzipped
    ├── sequencing_summary.txt.gz    # gzipped
    ├── fast5/                       # fast5 folder
    |    ├── 1.tar                   # each tar contains ~4000 fast5 files
    |    └── 2.tar
    |    └── 3.tar
    |    └── ...

## Inputs

It takes 3 files as input:

1.  fastq, paf, or flat (.gz)
2.  sequencing_summary.txt(.gz)
3.  name.index(.gz)

#### 1. fastq, paf, or flat

This is where the readIDs are collected, to be matched with their respective fast5 files for fetching. The idea being, that some form of selection has occurred to generate the files.

In the case of a **fastq**, it may be filtered for all the reads above a certain quality, or from a particular barcode after running barcode detection.

For the **paf** file, it is an alignment output of minimap2. This can be used to fetch only the fast5 files that align to some reference, or has been filtered to only contain the reads that align to a particular region of interest.

A **flat** file in this case is just a file that contains a list of readIDs, one on each line. This allows the user to generate any list of reads to fetch from any other desired method.

Each of these files can be gzipped or not.

See examples below for example test cases.

#### 2. Sequencing summary

The `sequencing_summary.txt` file is created by the basecalling software, (Albacore, Guppy), and contains information about each read, including the readID and fast5 file name, along with length, quality scores, and potentially barcode information.

There is a shortcut method in which you can use the `sequencing_summary.txt` only, without the need for a fastq, paf, or flat file. In this case, leave the `-q`, `-f`, `-r` fields empty.

This file can be gzipped or not.

#### 3. Building the index

How the index is built depends on which file structure you are using. It will work with both tarred and un-tarred file structures. Tarred is preferred.

##### - Raw structure (not preferred)

```bash
for file in $(pwd)/reads/*/*;do echo $file; done >> name.index

gzip name.index
```

##### - Local basecalled structure

```bash
for file in $(pwd)/reads.tar; do echo $file; tar -tf $file; done >> name.index

gzip name.index
```

##### - Parallel basecalled structure

```bash
for file in $(pwd)/fast5/*fast5.tar; do echo $file; tar -tf $file; done >> name.index
```

If you have multiple experiments, then cat them all together and gzip.

```bash
for file in ./*.index; do cat $file; done >> ../all.name.index

gzip all.name.index
```

## Instructions for use

Download the repository:

    git clone https://github.com/Psy-Fer/fast5_fetcher.git

If using MacOS, and NOT using homebrew, install it here:

    https://brew.sh/

then install gnu-tar with:

    brew install gnu-tar

### Quick start

Basic use on a local computer

**fastq**

```bash
python fast5_fetcher.py -q my.fastq.gz -s sequencing_summary.txt.gz -i name.index.gz -o ./fast5
```

**paf**

```bash
python fast5_fetcher.py -p my.paf -s sequencing_summary.txt.gz -i name.index.gz -o ./fast5
```

**flat**

```bash
python fast5_fetcher.py -f my_flat.txt.gz -s sequencing_summary.txt.gz -i name.index.gz -o ./fast5
```

**sequencing_summary.txt only**

```bash
python fast5_fetcher.py -s sequencing_summary.txt.gz -i name.index.gz -o ./fast5
```

See examples below for use on an **HPC** using **SGE**

## fast5_fetcher.py

#### Full usage

    usage: fast5_fetcher.py [-h] [-q FASTQ | -p PAF | -f FLAT] [-s SEQ_SUM]
                        [-i INDEX] [-o OUTPUT] [-z]

    fast_fetcher - extraction of specific nanopore fast5 files

    optional arguments:
    -h, --help            show this help message and exit
    -q FASTQ, --fastq FASTQ
                        fastq.gz for read ids
    -p PAF, --paf PAF     paf alignment file for read ids
    -f FLAT, --flat FLAT  flat file of read ids
    -s SEQ_SUM, --seq_sum SEQ_SUM
                        sequencing_summary.txt.gz file
    -i INDEX, --index INDEX
                        index.gz file mapping fast5 files in tar archives
    -o OUTPUT, --output OUTPUT
                        output directory for extracted fast5s
    -z, --pppp            Print out tar commands in batches for further
                        processing

## Examples

Fast5 Fetcher was originally built to work with **Sun Grid Engine** (SGE), exploiting the heck out of array jobs. Although it can work locally and on untarred file structures, when operating on multiple sequencing experiments, with file structures scattered across a file system, is when fast5 fetcher starts to make a difference.

### SGE examples

After creating the fastq/paf/flat, sequencing_summary, and index files, create an SGE file.

Note the use of `${SGE_TASK_ID}` to use the array job as the pointer to a particular file

#### After barcode demultiplexing

Given a similar structure and naming convention, it is possible to group the fast5 files by barcode in the following manner.

    ├── BC_1.fastq.gz                # Barcode 1
    ├── BC_2.fastq.gz                # Barcode 2
    ├── BC_3.fastq.gz                # ...
    ├── BC_4.fastq.gz          
    ├── BC_5.fastq.gz            
    ├── BC_6.fastq.gz           
    ├── BC_7.fastq.gz           
    ├── BC_8.fastq.gz           
    ├── BC_9.fastq.gz           
    ├── BC_10.fastq.gz           
    ├── BC_11.fastq.gz            
    ├── BC_12.fastq.gz            
    ├── unclassified.fastq.gz        # unclassified reads (skipped by fast5_fetcher in this example, rename BC_13 to simple fold it into the example)        
    ├── sequencing_summary.txt.gz    # gzipped
    ├── barcoded.index.gz            # index file containing fast5 file paths
    ├── fast5/                       # fast5 folder, unsorted
    |    ├── 1.tar                   # each tar contains ~4000 fast5 files
    |    └── 2.tar
    |    └── 3.tar
    |    └── ...

#### fetch.sge

```bash
# activate virtual python environment
# most HPC will use something like "module load"
source ~/work/venv2714/bin/activate

# Creaete output directory to take advantage of NVME drives on cluster local
mkdir ${TMPDIR}/fast5

# Run fast_fetcher on each barcode after demultiplexing
time python fast5_fetcher.py -r ./BC_${SGE_TASK_ID}.fastq.gz -s sequencing_summary.txt.gz -i barcoded.index.gz -o ${TMPDIR}/fast5/

# tarball the extracted reads into a single tar file
# Can also split the reads into groups of ~4000 if needed
tar -cf ${TMPDIR}/BC_${SGE_TASK_ID}_fast5.tar --transform='s/.*\///' ${TMPDIR}/fast5/*.fast5
# Copy from HPC drives to working dir.
cp ${TMPDIR}/BC_${SGE_TASK_ID}_fast5.tar ./
```

#### Create CMD and launch

```bash
# current working dir, with 1 CPU, array jobs 1 to 12
# Modify memory settings as required
CMD="qsub -cwd -V -pe smp 1 -N F5F -S /bin/bash -t 1-12 -l mem_requested=20G,h_vmem=20G,tmp_requested=500G ./fetch.sge"

echo $CMD && $CMD
```

## batch_tater.py

Potato scripting engaged

This is designed to run on the output files from `fast5_fetcher.py` using option `-z`. This writes out file lists for each tarball that contains reads you want to process. Then `batch_tater.py` can read those files, to open the individual tar files, and extract the files, meaning the file is only opened once.

A recent test using the -z option on ~2.2Tb of data, across ~11/27 million files took about 10min (1CPU) to write and organise the file lists with fast5_fetch.py, and about 20s per array job to extract and repackage with batch_tater.py.

This is best used when you want to do something all at once and filter your reads. Other approaches may be better when you are demultiplexing.

#### Usage:

Run on SGE using array jobs as a hacky way of doing multiprocessing.
Also, helps check when things go wrong, and easy to relaunch failed jobs.

#### batch.sge

```bash
source ~/work/venv2714/bin/activate

FILE=$(ls ./fast5/ | sed -n ${SGE_TASK_ID}p)
BLAH=fast5/${FILE}

mkdir ${TMPDIR}/fast5

time python batch_tater.py tater_master.txt ${BLAH} ${TMPDIR}/fast5/

echo "size of files:" >&2
du -shc ${TMPDIR}/fast5/ >&2
echo "extraction complete!" >&2
echo "Number of files:" >&2
ls ${TMPDIR}/fast5/ | wc -l >&2

echo "copying data..." >&2

tar -cf ${TMPDIR}/batch.${SGE_TASK_ID}.tar --transform='s/.*\///' ${TMPDIR}/fast5/*.fast5
cp ${TMPDIR}/batch.${SGE_TASK_ID}.tar ./batched_fast5/
```

#### Create CMD and launch

```bash
CMD="qsub -cwd -V -pe smp 1 -N batch -S /bin/bash -t 1-10433 -tc 80 -l mem_requested=20G,h_vmem=20G,tmp_requested=200G ../batch.sge"

echo $CMD && $CMD
```

## Acknowledgements

I would like to thank the rest of my lab (Shaun Carswell, Kirston Barton, Kai Martin) in Genomic Technologies team from the [Garvan Institute](https://www.garvan.org.au/) for their feedback on the development of this tool.

## Cite

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.1413903.svg)](https://doi.org/10.5281/zenodo.1413903)

James M. Ferguson, & Martin A. Smith. (2018, September 12). Psy-Fer/fast5_fetcher: Initial release of fast5_fetcher (Version v1.0). Zenodo. <http://doi.org/10.5281/zenodo.1413903>

## License

[The MIT License](https://opensource.org/licenses/MIT)
