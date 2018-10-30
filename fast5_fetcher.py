import os
import sys
import gzip
import io
import subprocess
import traceback
import argparse
import platform
from functools import partial
'''

    James M. Ferguson (j.ferguson@garvan.org.au)
    Genomic Technologies
    Garvan Institute
    Copyright 2017

    fast5_fetcher is designed to help manage fast5 file data storage and organisation.
    It takes 3 files as input: fastq/paf/flat, sequencing_summary, index

    --------------------------------------------------------------------------------------
    version 0.0   - initial
    version 0.2   - added argparser and buffered gz streams
    version 0.3   - added paf input
    version 0.4   - added read id flat file input
    version 0.5   - pppp print output instead of extracting
    version 0.6   - did a dumb. changed x in s to set/dic entries O(n) vs O(1)
    version 0.7   - cleaned up a bit to share and removed some hot and steamy features
    version 0.8   - Added functionality for un-tarred file structures and seq_sum only
    version 1.0   - First release
    version 1.1   - refactor with dicswitch and batch_tater updates
    version 1.1.1 - Bug fix on --transform method, added OS detection

    TODO:
        - Python 3 compatibility
        - autodetect file structures
        - autobuild index file - make it a sub script as well
        - Consider using csv.DictReader() instead of wheel building
        - flesh out batch_tater and give better examples and clearer how-to
        - options to build new index/SS of fetched fast5s

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
    parser.add_argument("--OSystem", default=platform.system(),
                        help="running operating system - leave default unless doing odd stuff")
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
        else:
            try:
                extract_file(args, p, f)
            except:
                traceback.print_exc()
                print >> sys.stderr, "Failed to extract:", p, f
    # For each .tar file, write a file with the tarball name as filename.tar.txt
    # and contains a list of files to extract - input for batch_tater.py
    if args.pppp:
        with open("tater_master.txt", 'w') as m:
            for i in p_dic:
                fname = "tater_" + i.split('/')[-1] + ".txt"
                m_entry = "{}\t{}".format(fname, i)
                m.write(m_entry)
                m.write('\n')
                with open(fname, 'w') as f:
                    for j in p_dic[i]:
                        f.write(j)
                        f.write('\n')

    print >> sys.stderr, "done!"


def dicSwitch(i):
    '''
    A switch to handle file opening and reduce duplicated code
    '''
    open_method = {
        "gz": gzip.open,
        "norm": open
    }
    return open_method[i]


def get_fq_reads(fastq):
    '''
    read fastq file and extract read ids
    quick and dirty to limit library requirements - still bullet fast
    '''
    c = 0
    read_ids = set()
    if fastq.endswith('.gz'):
        f_read = dicSwitch('gz')
    else:
        f_read = dicSwitch('norm')
    with f_read(fastq, 'rb') as fq:
        if fastq.endswith('.gz'):
            fq = io.BufferedReader(fq)
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
    if reads.endswith('.gz'):
        f_read = dicSwitch('gz')
    else:
        f_read = dicSwitch('norm')
    with f_read(reads, 'rb') as fq:
        if reads.endswith('.gz'):
            fq = io.BufferedReader(fq)
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
        f_read = dicSwitch('gz')
    else:
        f_read = dicSwitch('norm')
    with f_read(filename, 'rb') as fq:
        if filename.endswith('.gz'):
            fq = io.BufferedReader(fq)
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
        f_read = dicSwitch('gz')
    else:
        f_read = dicSwitch('norm')
    with f_read(seq_sum, 'rb') as sz:
        if seq_sum.endswith('.gz'):
            sz = io.BufferedReader(sz)
        for line in sz:
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
        f_read = dicSwitch('gz')
    else:
        f_read = dicSwitch('norm')
    # detect normal or tars
    with f_read(index_file, 'rb') as idz:
        if index_file.endswith('.gz'):
            idz = io.BufferedReader(idz)
        for line in idz:
            line = line.strip('\n')
            c += 1
            if c > 10:
                break
            if line.endswith('.tar'):
                tar = True
                break
    # extract paths
    with f_read(index_file, 'rb') as idz:
        if index_file.endswith('.gz'):
            idz = io.BufferedReader(idz)
        for line in idz:
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


def extract_file(args, path, filename):
    '''
    Do the extraction.
    I was using the tarfile python lib, but honestly, it sucks and was too volatile.
    if you have a better suggestion, let me know :)
    That --transform hack is awesome btw. Blows away all the leading folders. use
    cp for when using untarred structures. Not recommended, but here for completeness.

    --transform not working on MacOS. Need to use gtar
    Thanks to Kai Martin for picking that one up!

    '''
    OSystem = ""
    OSystem = args.OSystem
    save_path = args.output
    if path.endswith('.tar'):
        if OSystem in ["Linux", "Windows"]:
            cmd = "tar -xf {} --transform='s/.*\///' -C {} {}".format(
                path, save_path, filename)
        elif OSystem == "Darwin":
            cmd = "gtar -xf {} --transform='s/.*\///' -C {} {}".format(
                path, save_path, filename)
        else:
            print >> sys.stderr, "Unsupported OSystem, trying Tar anyway, OS:", OSystem
            cmd = "tar -xf {} --transform='s/.*\///' -C {} {}".format(
                path, save_path, filename)
    else:
        cmd = "cp {} {}".format(filename, os.path.join(
            save_path, filename.split('/')[-1]))
    subprocess.call(cmd, shell=True, executable='/bin/bash')


if __name__ == '__main__':
    main()
