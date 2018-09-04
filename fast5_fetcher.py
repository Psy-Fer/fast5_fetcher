import os
import sys
import gzip
import io
import subprocess
import traceback
import argparse
from functools import partial
'''

    James M. Ferguson (j.ferguson@garvan.org.au)
    Genomic Technologies
    Garvan Institute
    Copyright 2017

    Fast5 Fetcher is designed to help manage fast5 file data storage and organisation.
    It takes 3 files as input: fastq/paf/flat, sequencing_summary, index

    --------------------------------------------------------------------------------------
    version 1.0 - initial
    version 1.2 - added argparser and buffered gz streams
    version 1.3 - added paf input
    version 1.4 - added read id flat file input
    version 1.5 - pppp print output instead of extracting
    version 1.6 - did a dumb. changed x in s to set/dic entries O(n) vs O(1)
    version 1.7 - cleaned up a bit to share and removed some hot and steamy features
    version 1.8 - Added functionality for un-tarred file structures and seq_sum only


    TODO:
        - Python 3 compatibility
        - autodetect file structures
        - autobuild index file - make it a sub script as well
        - Consider using csv.DictReader() instead of wheel building

    -----------------------------------------------------------------------------
    MIT License

    Copyright (c) 2017 James Ferguson

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
'''


class MyParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)


def main():
    '''
    do the thing
    '''
    parser = MyParser(
        description="fast_fetcher - extraction of specific nanopore fast5 files")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-q", "--fastq",
                       help="fastq.gz for read ids")
    group.add_argument("-p", "--paf",
                       help="paf alignment file for read ids")
    group.add_argument("-f", "--flat",
                       help="flat file of read ids")
    # parser.add_argument("-b", "--fast5",
    #                    help="fast5.tar path to extract from - individual")
    parser.add_argument("-s", "--seq_sum",
                        help="sequencing_summary.txt.gz file")
    parser.add_argument("-i", "--index",
                        help="index.gz file mapping fast5 files in tar archives")
    parser.add_argument("-o", "--output",
                        help="output directory for extracted fast5s")
    # parser.add_argument("-t", "--procs", type=int,
    #                    help="Number of CPUs to use - TODO: NOT YET IMPLEMENTED")
    parser.add_argument("-z", "--pppp", action="store_true",
                        help="Print out tar commands in batches for further processing")
    args = parser.parse_args()

    # print help if no arguments given
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    print >> sys.stderr, "Starting things up!"

    p_dic = {}
    if args.pppp:
        print >> sys.stderr, "PPPP state! Not extracting, exporting tar commands"

    ids = []
    if args.fastq:
        ids = get_fq_reads(args.fastq)
    elif args.paf:
        ids = get_paf_reads(args.paf)
    elif args.flat:
        ids = get_flat_reads(args.flat)
    filenames = get_filenames(args.seq_sum, ids)

    '''
    if args.fast5:
        paths = get_paths(args.index, filenames, args.fast5)
        # place multiprocessing pool here
        # print >> sys.stderr, "All the paths: \n", paths
        print >> sys.stderr, "extracting..."
        for p, f in paths:
            if args.pppp:
                if p in p_dic:
                    p_dic[p].append(f)
                else:
                    p_dic[p] = [f]
                continue
            try:
                #print >> sys.stderr, "extracting:", p, f
                extract_file(p, f, args.output)
            except:
                traceback.print_exc()
                print >> sys.stderr, "Failed to extract:", p, f
    else:
    '''
    paths = get_paths(args.index, filenames)
    print >> sys.stderr, "extracting..."
    # place multiprocessing pool here
    for p, f in paths:
        if args.pppp:
            if p in p_dic:
                p_dic[p].append(f)
            else:
                p_dic[p] = [f]
            continue
        try:
            extract_file(p, f, args.output)
        except:
            traceback.print_exc()
            print >> sys.stderr, "Failed to extract:", p, f
    # For each .tar file, write a file with the tarball name as filename.tar.txt
    # and contains a list of files to extract - input for batch_tater.py
    for i in p_dic:
        fname = args.output + i.split('/')[-1] + ".txt"
        with open(fname, 'w') as f:
            for j in p_dic[i]:
                f.write(j)
                f.write('\n')

    print >> sys.stderr, "done!"


def get_fq_reads(fastq):
    '''
    read fastq file and extract read ids
    quick and dirty to limit library requirements - still bullet fast
    '''
    c = 0
    read_ids = set()
    if fastq.endswith('.gz'):
        with gzip.open(fastq, 'rb') as gz:
            fq = io.BufferedReader(gz)
            for line in fq:
                c += 1
                line = line.strip('\n')
                if c == 1:
                    idx = line.split()[0][1:]
                    read_ids.add(idx)
                elif c >= 4:
                    c = 0
    else:
        with open(fastq, 'rb') as fq:
            for line in fq:
                c += 1
                line = line.strip('\n')
                if c == 1:
                    idx = line.split()[0][1:]
                    read_ids.add(idx)
                elif c >= 4:
                    c = 0
    return read_ids


def get_paf_reads(reads):
    '''
    Parse paf file to pull read ids (from minimap2 alignment)
    '''
    read_ids = set()
    with open(reads, 'rb') as fq:
        for line in fq:
            line = line.strip('\n')
            line = line.split()
            read_ids.add(line[0])
    return read_ids


def get_flat_reads(filename):
    '''
    Parse a flat file separated by line breaks \n
    TODO: make @ symbol check once, as they should all be the same
    '''
    read_ids = set()
    check = True
    if filename.endswith('.gz'):
        with gzip.open(filename, 'rb') as gz:
            for line in io.BufferedReader(gz):
                line = line.strip('\n')
                if check:
                    if line[0] == '@':
                        x = 1
                    else:
                        x = 0
                    check = False
                idx = line[x:]
                read_ids.add(idx)
    else:
        with open(filename, 'rb') as fq:
            for line in fq:
                line = line.strip('\n')
                if check:
                    if line[0] == '@':
                        x = 1
                    else:
                        x = 0
                    check = False
                idx = line[x:]
                read_ids.add(idx)
    return read_ids


def get_filenames(seq_sum, ids):
    '''
    match read ids with seq_sum to pull filenames
    '''
    # for when using seq_sum for filtering, and not fq,paf,flat
    ss_only = False
    if not ids:
        ss_only = True

    head = True
    files = set()
    if seq_sum.endswith('.gz'):
        with gzip.open(seq_sum, 'rb') as sz:
            for line in io.BufferedReader(sz):
                if head:
                    head = False
                    continue
                line = line.strip('\n')
                line = line.split()
                if ss_only:
                    files.add(line[0])
                else:
                    if line[1] in ids:
                        files.add(line[0])
    else:
        with open(seq_sum, 'rb') as ss:
            for line in ss:
                if head:
                    head = False
                    continue
                line = line.strip('\n')
                line = line.split()
                if ss_only:
                    files.add(line[0])
                else:
                    if line[1] in ids:
                        files.add(line[0])
    return files


def get_paths(index_file, filenames, f5=None):
    '''
    Read index and extract full paths for file extraction
    '''
    tar = False
    paths = []
    c = 0
    if index_file.endswith('.gz'):
        with gzip.open(index_file, 'rb') as idz:
            for line in io.BufferedReader(idz):
                line = line.strip('\n')
                c += 1
                if c > 10:
                    break
                if line.endswith('.tar'):
                    tar = True
                    break
    else:
        with open(index_file, 'rb') as idx:
            for line in idx:
                line = line.strip('\n')
                c += 1
                if c > 10:
                    break
                if line.endswith('.tar'):
                    tar = True
                    break
    '''
    if f5:
        locker = False
        if index_file.endswith('.gz'):
            with gzip.open(index_file, 'rb') as idz:
                for line in io.BufferedReader(idz):
                    line = line.strip('\n')
                    if line.endswith('.tar'):
                        if line.split('/')[-1] == f5.split('/')[-1]:
                            path = line
                            locker = False
                        else:
                            locker = True
                    elif line.endswith('.fast5') and not locker:
                        f = line.split('/')[-1]
                        if f in filenames:
                            paths.append([path, line])
                    else:
                        continue
        else:
            with open(index_file, 'rb') as idx:
                for line in idx:
                    line = line.strip('\n')
                    if line.endswith('.tar'):
                        if line.split('/')[-1] == f5.split('/')[-1]:
                            path = line
                            locker = False
                        else:
                            locker = True
                    elif line.endswith('.fast5') and not locker:
                        f = line.split('/')[-1]
                        if f in filenames:
                            paths.append([path, line])
                    else:
                        continue
    else:
    '''
    if index_file.endswith('.gz'):
        with gzip.open(index_file, 'rb') as idz:
            for line in io.BufferedReader(idz):
                line = line.strip('\n')
                if tar:
                    if line.endswith('.tar'):
                        path = line
                    elif line.endswith('.fast5'):
                        f = line.split('/')[-1]
                        if f in filenames:
                            paths.append([path, line])
                    else:
                        continue
                else:
                    if line.endswith('.fast5'):
                        f = line.split('/')[-1]
                        if f in filenames:
                            paths.append(['', line])
                    else:
                        continue
    else:
        with open(index_file, 'rb') as idx:
            for line in idx:
                line = line.strip('\n')
                if tar:
                    if line.endswith('.tar'):
                        path = line
                    elif line.endswith('.fast5'):
                        f = line.split('/')[-1]
                        if f in filenames:
                            paths.append([path, line])
                    else:
                        continue
                else:
                    if line.endswith('.fast5'):
                        f = line.split('/')[-1]
                        if f in filenames:
                            paths.append(['', line])
                    else:
                        continue
    return paths


def extract_file(path, filename, save_path):
    '''
    Do the extraction.
    I was using the tarfile python lib, but honestly, it sucks and was too volatile.
    if you have a better suggestion, let me know :)
    That --transform hack is awesome btw. Blows away all the leading folders. use it
    cp for when using untarred structures. Not recommended, but here for completeness.
    '''
    if path.endswith('.tar'):
        cmd = "tar -xf {} --transform='s/.*\///' -C {} {}".format(
            path, save_path, filename)
    else:
        cmd = "cp {} {}".format(filename, os.path.join(
            save_path, filename.split('/')[-1]))
    subprocess.call(cmd, shell=True, executable='/bin/bash')


if __name__ == '__main__':
    main()
