import datetime
import math
import os
import pickle
import random
import re
import subprocess
import sys
from pathlib import Path
from socket import timeout

import debugpy
import ray

#import mctree if inside experiment dir
sys.path.append("../../../src/")
import mctree

import mctree.tool.invoke as invoke
from mctree import make_ccline
from mctree.tool.support import first_defined, mkpath

#sys.path.append("../../../src/")
#from mctree import make_ccline
#thisscript = Path(__file__)
#print("thisscript: ",thisscript)
#sys.path.insert(0,str( (thisscript.parent.parent.parent / 'src').absolute() ))



class Plopper:
    def __init__(self,sourcefile,outputdir):

        # Initilizing global variables
        self.sourcefile = sourcefile
        #self.outputdir = outputdir+"/tmp_files"
        self.outputdir = outputdir

        #if not os.path.exists(self.outputdir):
            #os.makedirs(self.outputdir)

        #Delete after read
        self.ccargs = pickle.load(open(outputdir+"/ccargs","rb"))
        self.execopts = pickle.load(open(outputdir+"/execopts","rb"))
        
        #Experiments Counter
        self.num_experiment = 0


    #Creating a dictionary using parameter label and value
    def createDict(self, x, params):
        dictVal = {}
        for p, v in zip(params, x):
            dictVal[p] = v
        return(dictVal)


    #Replace the Markers in the source file with the corresponding Pragma values
    def plotValues(self, dictVal, inputfile, outputfile):
        with open(inputfile, "r") as f1:
            buf = f1.readlines()
#             param = "" #string to hold the parameters in case we cuda is used
#             global cuda
#             cuda = False
#             for line in buf: #check if we are using cuda. If yes, collect the parameters.
#                 if "POLYBENCH_2D_ARRAY_DECL_CUDA" or "POLYBENCH_3D_ARRAY_DECL_CUDA" or "POLYBENCH_1D_ARRAY_DECL_CUDA"in line:
#                     cuda = True
        
        with open(outputfile, "w") as f2:
            for line in buf:
                stop = False
                modify_line = line
                try:
                    while not stop:
                        if not re.search(r"#P([0-9]+)", modify_line):
                            stop = True
                        for m in re.finditer(r"#P([0-9]+)", modify_line):
                            modify_line = re.sub(r"#P"+m.group(1), dictVal["P"+m.group(1)], modify_line)
                except Exception as e:
                    print("we got exception", e)
                    print(dictVal)
                if modify_line != line:
                    f2.write(modify_line)
                else:
                    #To avoid writing the Marker
                    f2.write(line)
    
    
    # Function to find the execution time of the interim file, and return the execution time as cost to the search module
    #@ray.remote
    def findRuntime(self, x, params):

        
        # 5678 is the default attach port in the VS Code debug configurations. Unless a host and port are specified, host defaults to 127.0.0.1
        
        DEBUG_MODE = False
        DEBUG_MODE_RAY = False
        if DEBUG_MODE:
            debugpy.listen(5672)
            print("Waiting for debugger attach")
            debugpy.wait_for_client()
            debugpy.breakpoint()
            print('breaking now')
            #breakpoint()
        if DEBUG_MODE_RAY:
            breakpoint()
        
        

        outputdir_exp = self.outputdir+"/Experiment_"+str(self.num_experiment)
        if not os.path.exists(outputdir_exp):
            os.makedirs(outputdir_exp)
        self.num_experiment+=1
        
        #compile_success = False
        interimfile = ""
        exetime = math.inf
        counter = random.randint(1, 10001) # To reduce collision increasing the sampling intervals

        interimfile = outputdir_exp+"/tmp_"+str(counter)+".c"

        # Generate intermediate file
        dictVal = self.createDict(x, params)
        self.plotValues(dictVal, self.sourcefile, interimfile)

        #compile and find the execution time
        tmpbinary = interimfile[:-2]
       
        #tmpdir = '/'.join([i for i in interimfile.split('/')[:-1]])

        kernel_idx = self.sourcefile.rfind('/')
        kernel_exp_dir = self.sourcefile[:kernel_idx]
        #utilities_dir = kernel_exp_dir+"/utilities"

        #commonflags = f"""-DEXTRALARGE_DATASET -DPOLYBENCH_TIME -I{utilities_dir} -I{kernel_dir} {interimfile} {utilities_dir}/polybench.c -o {tmpbinary} -lm -g """
        
        #gcc_cmd = f"""clang -O2 -fopenmp -fopenmp-targets=nvptx64 -Xopenmp-target -march=sm_75 {commonflags} -I/soft/compilers/cuda/cuda-11.4.0/include -L/soft/compilers/cuda/cuda-11.4.0/lib64 -Wl,-rpath=/soft/compilers/cuda/cuda-11.4.0/lib64 -lcudart_static -ldl -lrt -pthread"""
        
        #X- MCtree x Ytopt
        #clang_cmd = f"""/home/skale/gpfs/libs/llvm-dbg-PCL/bin/clang {interimfile} -I/home/skale/gpfs/libs/llvm-dbg-PCL/projects/openmp/runtime/src -I/home/skale/gpfs/libs/llvm-dbg-PCL/runtimes/runtimes-bins/openmp/runtime/src -L/home/skale/gpfs/libs/llvm-dbg-PCL/runtimes/runtimes-bins/openmp/runtime/src -mllvm -polly-position=early -O3 -march=native -I/home/skale/projects/summer22/mctree/codes/oned -mllvm -polly-only-func=foo -iquote /home/skale/projects/summer22/mctree/codes/oned -iquote /home/skale/projects/summer22/mctree/codes/oned -ferror-limit=1 -mllvm -polly -mllvm -polly-process-unprofitable -mllvm -polly-reschedule=0 -mllvm -polly-pattern-matching-based-opts=0 -fopenmp -mllvm -polly-omp-backend=LLVM -mllvm -polly-scheduling=static -Werror=pass-failed -o {tmpbinary}"""

        #Add polybenc.c to ccfiles
        #interimfile = mkpath(interimfile)
        ccfiles = [interimfile] + [ccfile for ccfile in self.ccargs.ccfiles if "polybench.c" in str(ccfile)]
        ccfiles = [mkpath(ccfile) for ccfile in ccfiles]
        #X- Reusing the invoke.diag from MCtree
        #Collecting command lines
        cmdline = make_ccline(self.ccargs, ccfiles=ccfiles, outfile=tmpbinary)
        print("Kernel cmdline: ")
        print(cmdline)

        cc_text = mkpath(outputdir_exp)/"cc.txt"
        exec_text = mkpath(outputdir_exp)/"exec.txt"

        use_invoke_diag = True

        if use_invoke_diag:
            
            print("wait")

            #Compiling
            try:
                invoke.diag(*cmdline, cwd=outputdir_exp, onerror=invoke.Invoke.EXCEPTION, std_prefixed=cc_text)
                #compile_success = True
            except subprocess.CalledProcessError:
                # Compilation failed; illegal program
                print("compile failed")
                return exetime

            #Appending tmpbinary with exe.pl from mctree.tool
            #X- DO NOT add exe_pl_path to make_ccline(outfile=tmpbinary). Its for YTopt run only
            exe_pl_path = os.path.dirname(os.path.abspath(mctree.tool.__file__))
            exe_pl = exe_pl_path+"/exe.pl"
            #tmpbinary = ' '.join([exe_pl,tmpbinary])
            exec_cmd = [exe_pl,tmpbinary]
            
            #Execution

            #X- 1. We lost self.execopts.args somewhere along the road. Might be
            #just an issue with partial run used for testing. Must fix regardless --FIXED
            #2. Passing exe.pl along with binary doesn't work with invoke.diag --FIXED
            
            try:
                #run_exec(experiment=experiment,cwd=expdir,exefile=exefile,execopts=execopts)
                polybench_time = self.execopts.polybench_time
                #Append tmbinary with path(mcroot)/exe.pl?
                p = invoke.diag(exec_cmd, *self.execopts.args,timeout=self.execopts.timeout, std_prefixed=exec_text,
                appendenv={'LD_LIBRARY_PATH': self.execopts.ld_library_path}, cwd=outputdir_exp,onerror=invoke.Invoke.EXCEPTION,return_stdout=polybench_time)

                
                if polybench_time:
                    compiletime = datetime.timedelta(seconds=float(p.stdout.rstrip().splitlines()[-1]))
                    exetime = compiletime.microseconds / (10**6) #micrsoseconds -> seconds
                    print(f"Execution completed in {p.walltime}; polybench measurement: {compiletime}")
                else:
                    exetime = p.walltime.microseconds / (10**6)
                    print(f"Execution completed in {p.walltime}")
            except subprocess.TimeoutExpired:
                # Assume failure
                print("Execution timeout reached")
                #raise Exception("Execution incomplete")
                return exetime
                #return 1
            
            #return execution time as cost
            print("DICT_VAL, EXETIME",dictVal,exetime)
            return exetime
        
        else:

            #X- Without reusing invoke.diag from MCTree
            #Remove Posixpath links
            clang_cmd = [str(cmd) if isinstance(cmd,Path) else cmd for cmd in cmdline]
            clang_cmd = " ".join([cmd for cmd in clang_cmd])

            exe_pl_path = os.path.dirname(os.path.abspath(mctree.tool.__file__))
            exe_pl = exe_pl_path+"/exe.pl"
            tmpbinary = ' '.join([exe_pl,tmpbinary])
            run_cmd = "LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:"+self.execopts.ld_library_path + " " + tmpbinary

            #compile_log = open(outputdir_exp"")
            #Compiling
            compilation_status = subprocess.run(clang_cmd, shell=True, stderr=subprocess.PIPE)

            if compilation_status.returncode == 0 :
                execution_status = subprocess.run(run_cmd, shell=True, stdout=subprocess.PIPE)
                exetime = float(execution_status.stdout.decode('utf-8'))

                if exetime == 0:
                    exetime = 1

            else:
                print(compilation_status.stderr)
                print("compile failed")
                #print(run_cmd)
                #raise Exception("Check kernel")
                #exetime = math.inf

            #return execution time as cost
            print("DICT_VAL, EXETIME",dictVal,exetime)
            return exetime
        
        """
        #X- Without reusing invoke.diag from MCTree
        #X- Add polybench.c to interim file
        clang_cmd = make_ccline(self.ccargs, ccfiles=[interimfile], outfile=tmpbinary)
        #Remove Posixpath links
        clang_cmd = [str(cmd) if isinstance(cmd,Path) else cmd for cmd in clang_cmd]
        clang_cmd = " ".join([cmd for cmd in clang_cmd])
        print(clang_cmd)

        
        run_cmd = "LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:"+self.execopts.ld_library_path + " " + kernel_dir + "/exe.pl " + tmpbinary

        #run_cmd = kernel_dir + "/exe.pl " + tmpbinary
#         print (run_cmd)
        #Find the compilation status using subprocess
        compilation_status = subprocess.run(clang_cmd, shell=True, stderr=subprocess.PIPE)

        #Find the execution time only when the compilation return code is zero, else return infinity
        if compilation_status.returncode == 0 :
            execution_status = subprocess.run(run_cmd, shell=True, stdout=subprocess.PIPE)
            exetime = float(execution_status.stdout.decode('utf-8'))
            if exetime == 0:
                exetime = 1
        else:
            print(compilation_status.stderr)
            print("compile failed")
            print(run_cmd)
            raise Exception("Check kernel")
            exetime = math.inf
        
        """
        #return execution time as cost
        #return exetime