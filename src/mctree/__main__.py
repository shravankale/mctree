#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, json, pickle, subprocess
import tempfile
import contextlib
import argparse

from numpy import append
from mctree import *
import mctree.tool.invoke as invoke
from mctree.tool.support import *
import mctree 
#from mctree import ParameterCounter
#import mctree.ytopt_parameter_counter as ypc
#from mctree.tool.support import process_ytopt_results

# Decorator
commands = {}
def subcommand(name):
    def command_func(_func):
        global commands
        commands[name] = _func
        return _func
    return command_func


@subcommand("autotune")
def autotune(parser, args):
    if parser:
        add_boolean_argument(parser, 'keep', default=True)
        parser.add_argument('--exec-arg', action='append')
        parser.add_argument('--exec-args', action='append')
        add_boolean_argument(parser, 'polybench-time')
        parser.add_argument('--ld-library-path', action='append')
        parser.add_argument('--outdir', action='append')
        parser.add_argument('--timeout', type=float,
                            help="Max exec time in seconds; default is no timout")
        parser.add_argument('ccline', nargs=argparse.REMAINDER)
    if args:
        ccargs = parse_cc_cmdline(args.ccline)
        ccargs.polybench_time = args.polybench_time

        execopts = argparse.Namespace()

        print("Argparse.Namespace() execopts: ", execopts, "\n")

        execopts.ld_library_path = None
        if args.ld_library_path != None:
            execopts.ld_library_path = ':'.join(args.ld_library_path)

        execopts.timeout = None
        if args.timeout != None:
            execopts.timeout = datetime.timedelta(seconds=args.timeout)
        execopts.polybench_time = args.polybench_time

        execopts.args = shcombine(arg=args.exec_arg,args=args.exec_args)

        print("Argparse.Namespace() execopts: ", execopts, "\n")

        outdir = mkpath(args.outdir[0])
        print("Outdir path: ",outdir)
        num_experiments = 0

        DEBUG_MODE=True
        with contextlib.ExitStack() as stack:
            if args.keep and not DEBUG_MODE:
                d = tempfile.mkdtemp(dir=outdir, prefix='mctree-')
            elif DEBUG_MODE:
                d = str(outdir)+"/mctree-dbg"
                if not os.path.exists(d):
                    os.makedirs(d)
                else:
                    import shutil
                    shutil.rmtree(d)
                    os.makedirs(d)
                    """for file in os.listdir(d):
                        if os.path.isfile(file):
                            os.remove(file)
                    """
            else:
                d = stack.enter_context(tempfile.TemporaryDirectory(dir=outdir, prefix='mctree-'))
            d = mkpath(d)


            print("Path d in autotune subcommand: ",d)

            bestfile = d / 'best.txt'
            csvfile = d / 'experiments.csv'
            newbestcsvfile = d / 'newbest.csv'
            csvlog = csvfile.open('w+')
            newbestlog = newbestcsvfile.open('w+')

            root = extract_loopnests(d, ccargs=ccargs, execopts=execopts)
            print("Baseline is")
            print(root)
            print("")

            #X- Add a check to see if root is empty or has no nestexperiments

            def priorotyfunc(x): 
                return -math.inf if x.duration is None else x.duration.total_seconds()
            pq = PriorityQueue(root, key=priorotyfunc)
            closed = set()
            bestsofar = root

            csvlog.write(f"{root.expnumber},{root.duration.total_seconds()},{bestsofar.expnumber},{bestsofar.duration.total_seconds()}\n")
            newbestlog.write(f"{bestsofar.expnumber},{bestsofar.duration.total_seconds()}\n")

            while not pq.empty():
                item = pq.top()
                
                #X- Execution block
                if item.duration == None:
                    num_experiments += 1
                    run_experiment(d, item, ccargs=ccargs, execopts=execopts, 
                        writedot=num_experiments < 90, 
                        dotfilter=None,
                        dotexpandfilter=lambda n: n in closed,
                        root=root)
                    if item.duration == math.inf:
                        # Invalid pragmas? Remove experiment entirely
                        print("Experiment failed")
                        pq.pop()
                        continue

                    pq.update()
                    if bestsofar.duration > item.duration:
                        print(
                            f"New experiment better than old (old: {bestsofar.duration}, new: {item.duration})")
                        print(f"Path {item.exppath}\n")
                        print(item)
                        bestsofar = item
                        with bestfile.open('w+') as f:
                            f.write(f"Best experiment so far\n")
                            f.write(f"Time: {bestsofar.duration}\n")
                            f.write(f"Path: {bestsofar.exppath}\n\n")
                            for line in bestsofar.to_lines():
                                f.write(line)
                                f.write('\n')
                        newbestlog.write(f"{bestsofar.expnumber},{bestsofar.duration.total_seconds()}\n")
                        newbestlog.flush()
                    csvlog.write(f"{item.expnumber},{item.duration.total_seconds()},{bestsofar.expnumber},{bestsofar.duration.total_seconds()}\n")
                    csvlog.flush()
                    continue

                #X- Expansion block
                if not item in closed:
                    #X- Depth Control
                    #if False:
                    if item.depth > args.maxdepth:
                        #closed.add(item)
                        pq.pop()
                        continue

                    else:
                        print(f"Selecting best experiment {item.duration} for expansion")
                        for child in item.children():
                            pq.push(child)

                        closed.add(item)
                        continue

                if item in closed and item.duration != None:
                    pq.pop()

            print("No more experiments!!?")

@subcommand("export-loopnest-json")
def exportLoopnestJson(parser,args):
    #X- TODO Write a subcommand to export loopnest-json of a kernel
    return None


@subcommand("example")
def example(parser, args):
    if parser:
        add_boolean_argument(parser,'loopneststructure')
    if args:
        loopcounter = LoopCounter()
        example = Loop.createRoot()
        example.new_subloop(loopcounter).new_substmt()
        outer = example.new_subloop(loopcounter)
        outer.new_subloop(loopcounter).new_substmt()
        #outer.new_substmt()

        root = Experiment()
        root.nestexperiments.append(LoopNestExperiment(example, [], loopcounter))

        for line in as_dot(root, max_depth=args.maxdepth,loopneststructure=args.loopneststructure):
            print(line)
        return 0



@subcommand("jsonfile")
def jsonfile(parser, args):
    if parser:
        parser.add_argument('filename', nargs='+')
    if args:
        root = read_json(files=args.filename)
        for line in as_dot(root, max_depth=args.maxdepth):
            print(line)
        return 0

import mctree.ytoptgen as ytoptgen

"""
@subcommand("ytopt-problem")
def ytopt(parser, args):
    if parser:
        add_boolean_argument(parser, 'keep', default=True)
        parser.add_argument('filename', nargs='+')
        parser.add_argument('--outdir',type=pathlib.Path)
    if args:

        with contextlib.ExitStack() as stack:
            if args.keep:
                d = tempfile.mkdtemp(dir=args.outdir, prefix='ytopy-')
            else:
                d = stack.enter_context(tempfile.TemporaryDirectory(dir=outdir, prefix='ytopt-'))
            d = mkpath(d)

            print("Path d in ytopt subcommand: ",d)

            ytoptgen.gen_ytopt_problem(filename=args.filename,outdir=d, max_depth=args.maxdepth)
"""

@subcommand("ytopt-problem")
def ytopt(parser, args):
    if parser:
        #parser.add_argument('--filename', nargs='+')
        add_boolean_argument(parser, 'keep', default=True)
        add_boolean_argument(parser, 'polybench-time')
        parser.add_argument('--exec-arg', action='append')
        parser.add_argument('--exec-args', action='append')
        parser.add_argument('--ld-library-path', action='append')
        parser.add_argument('--outdir', action='store')
        parser.add_argument('--timeout', type=float,
                            help="Max exec time in seconds; default is no timout")
        parser.add_argument('ccline', nargs=argparse.REMAINDER)
    if args:

        DEBUG_MODE = True
        with contextlib.ExitStack() as stack:
            if args.keep and not DEBUG_MODE:
                d = tempfile.mkdtemp(dir=args.outdir, prefix='ytopy-')
            elif DEBUG_MODE:
                d = args.outdir+"/ytopt_dbg"
                if not os.path.exists(d):
                    os.makedirs(d)
                else:
                    import shutil
                    shutil.rmtree(d)
                    os.makedirs(d)   
            else:
                d = stack.enter_context(tempfile.TemporaryDirectory(dir=args.outdir, prefix='ytopt-'))
            d = mkpath(d)

            #Collecting ccargs and exeopts
            ccargs = parse_cc_cmdline(args.ccline)
            ccargs.polybench_time = args.polybench_time

            execopts = argparse.Namespace()

            execopts.ld_library_path = None
            if args.ld_library_path != None:
                execopts.ld_library_path = ':'.join(args.ld_library_path)

            #X- YTopt supports eval timeout passed as an arg to ytopt.search.ambs
            execopts.timeout = None
            if args.timeout != None:
                execopts.timeout = datetime.timedelta(seconds=args.timeout)
            execopts.polybench_time = args.polybench_time

            execopts.args = shcombine(arg=args.exec_arg,args=args.exec_args)

            #ccargs and execopts to be used by ytopt plopper.py
            pickle.dump(ccargs,open(d/"ccargs","wb"))
            pickle.dump(execopts,open(d/"execopts","wb"))

            loopnestfiles = extract_loopnests(d, ccargs, execopts, only_polly_dump_loopnest=True)
            #X- Pass only the kernel file to ytoptgen
            ytoptgen.gen_ytopt_problem(filename=loopnestfiles,outdir=d, max_depth=args.maxdepth)

            #if args.exec_ytopt:
            ytopt_search_cmd = "/home/skale/soft/anaconda3/envs/mctree/bin/python -W ignore::FutureWarning -m ytopt.search.ambs --evaluator ray --problem problem.Problem --max-evals=10 --learner RF"
            ytopt_exec_status = subprocess.run(ytopt_search_cmd, shell=True, cwd=str(d),  stdout=subprocess.PIPE) #stderr=subprocess.PIPE 
            
            #X- Add try-catch block for subprocess runs
            if ytopt_exec_status.stderr:
                print(ytopt_exec_status.stderr)

            pragma, elapsed_sec, objective_value = process_ytopt_results(str(d)+"/results.csv")
            print("Pragma: ",pragma)
            print("Elaspsed secs: ",elapsed_sec)
            print("Objective Value: ",objective_value)

            results = open(str(d)+"/results.csv","a")
            results.write("Top 1 result below: \n")
            results.write("Pragma: "+pragma+"\n")
            results.write("Elapsed secs: "+str(elapsed_sec)+"\n")
            results.write("Objective Value: "+str(objective_value))
            results.close()

            print("Fin.")




def main(argv: str) -> int:
    global transformers 
    parser = argparse.ArgumentParser(description="Loop transformation search tree proof-of-concept", allow_abbrev=False)

    parser.add_argument('--maxdepth', type=int, default=1)
    add_boolean_argument(parser, "--tiling", default=False)
    parser.add_argument('--tiling-sizes')
    add_boolean_argument(parser, "--threading", default=False)
    add_boolean_argument(parser, "--interchange", default=False)
    add_boolean_argument(parser, "--reversal", default=False)
    add_boolean_argument(parser, "--unrolling", default=False)
    add_boolean_argument(parser, "--unrolling-full", default=False)
    parser.add_argument('--unrolling-factors')
    add_boolean_argument(parser, "--unrolling-and-jam", default=False)
    #add_boolean_argument(parser, "--unrolling-and-jam-full", default=True)
    parser.add_argument('--unrolling-and-jam-factors')
    parser.add_argument('--packing-arrays',action='append')
    add_boolean_argument(parser, "--fission", default=False)
    add_boolean_argument(parser, "--fusion", default=False)
    add_boolean_argument(parser, "--parametric", default=False)
    add_boolean_argument(parser, "--all-transformations", default=False)

    subparsers = parser.add_subparsers(dest='subcommand')
    for cmd, func in commands.items():
        subparser = subparsers.add_parser(cmd)
        func(parser=subparser, args=None)
    args = parser.parse_args(str(v) for v in argv[1:])
    #args = parser.parse_args()
    

    if args.all_transformations:
        args.tiling = True
        args.threading = True
        args.interchange = True
        args.reversal = True
        args.unrolling = False
        args.unrolling_and_jam = False
        args.fission = True
        args.fusion = True

    if args.tiling:
        tilesizes = [4,16]
        if args.tiling_sizes != None:
            tilesizes = [int(s) for s in args.tiling_sizes.split(',')]
        if args.parametric:
            transformers.append(TilingParametric.get_factory(tilesizes))
        else:
            transformers.append(Tiling.get_factory(tilesizes))
    if args.threading:
        transformers.append(Threading.get_factory())
    if args.interchange:
        transformers.append(Interchange.get_factory())
    if args.reversal:
        transformers.append(Reversal.get_factory())
    if args.unrolling:
        
        if args.unrolling_full:
            transformers.append(UnrollingFull.get_factory())   

        factors = [2, 4, 8]
        if args.unrolling_factors != None:
            factors = [int(s) for s in args.unrolling_factors.split(',')]
        if args.parametric:
            transformers.append(UnrollingParametric.get_factory(factors))
        else:
            transformers.append(Unrolling.get_factory(factors))
    if args.unrolling_and_jam:
        factors = [2, 4, 8]
        if args.unrolling_and_jam_factors != None:
            factors = [int(s) for s in args.unrolling_and_jam_factors.split(',')]
        if args.parametric:
            transformers.append(UnrollingAndJamParametric.get_factory(factors))
        else:
            transformers.append(UnrollingAndJam.get_factory(factors))
            
    pack_arrays = set()
    if args.packing_arrays:
            pack_arrays = set(arr for arrlist in args.packing_arrays for arr in arrlist.split(','))
    if pack_arrays:
            transformers.append(ArrayPacking.get_factory(pack_arrays))
    if args.fission:
        transformers.append(Fission.get_factory())
    if args.fusion:
        transformers.append(Fusion.get_factory())

    print("Number of Transformers: ",len(transformers))
    #print("Transformers: ",transformers[0])
    #sys.exit(0)
    #print("Args: ",args)

    cmdlet = commands.get(args.subcommand)
    if not cmdlet:
        die("No command?")
    return cmdlet(parser=None, args=args)
