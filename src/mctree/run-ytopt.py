import subprocess,sys,os
sys.path.append("../../../src/")
#sys.path.append("../../../bin/")
#sys.path.append("/home/skale/projects/summer22/mctree/src")
#sys.path.append("/home/skale/projects/summer22/mctree/src/mctree/tool/")
#sys.path.append("../../src/")
from mctree.tool.support import process_ytopt_results
#from mctree.support import *
#from mctree.tool import *
#from mctree import *

"""from mctree import *
import mctree.tool.invoke as invoke
from mctree.tool.support import *"""



MAX_EVALS = 400
LEARNER = "RF"
d = f"/home/skale/projects/summer22/mctree/codes/gemm/ytopt-xtc9w8mf-me{MAX_EVALS}"
#if args.exec_ytopt:
ytopt_search_cmd = f"/home/skale/soft/anaconda3/envs/mctree/bin/python -W ignore::FutureWarning -m ytopt.search.ambs --evaluator ray --problem problem.Problem --max-evals={MAX_EVALS} --learner RF"
print("YTOPT_SEARCH_CMD: ",ytopt_search_cmd)
ytopt_exec_status = subprocess.run(ytopt_search_cmd, shell=True, cwd=d,  stdout=subprocess.PIPE) #stderr=subprocess.PIPE 

#X- Add try-catch block for subprocess runs
if ytopt_exec_status.stderr:
    print(ytopt_exec_status.stderr)

pragma, elapsed_sec, objective_value = process_ytopt_results(d+"/results.csv")
print("Pragma: ",pragma)
print("Elaspsed secs: ",elapsed_sec)
print("Objective Value: ",objective_value)

results = open(d+f"/results.csv","a")
results.write("Top 1 result below: \n")
results.write("Pragma: "+pragma+"\n")
results.write("Elapsed secs: "+str(elapsed_sec)+"\n")
results.write("Objective Value: "+str(objective_value))
results.close()

print("Fin.")