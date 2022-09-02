#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from mctree import *
import mctree 
import pathlib
from .tool.support import *
import mctree.tool.ytopt_parameter_counter as ypc

#ypc.init()

escaperules = { "'": r"\'", '\n': r'\n' }
def pyescape(s):
    if isinstance(s,str):
        return '"' + ''.join(escaperules.get(c) if c in escaperules else c for c in s) + '"'
    return str(s)


def pylist(l):
    return '[' + ', '.join(pyescape(e) for e in l) + ']'



#p = 0
#p=ypc.p
params = []
experiment_to_param = dict()
def param_for_experiment(experiment):
    global p, params, experiment_to_param
    if param := experiment_to_param.get(experiment):
        return param
    #param = f"P{ypc.p}"
    param = f"P{ypc.p.nextParamID()}"
    experiment_to_param[experiment] = param
    params.append(param)
    #ypc.p += 1
    return param


condnames = []
def new_cond():
    global condnames
    result = f"c{len(condnames)}"
    condnames.append(result)
    return result 


# TODO: Consolidate with same functionality from run_experiment 
def prepare_cfiles(experiment, outdir):
    ccfiles = set()

    for x in experiment.nestexperiments:
        loops = set()
        rootloopnestexperiment = x
        while rootloopnestexperiment.derived_from != None:
            rootloopnestexperiment = rootloopnestexperiment.derived_from

        for loop in rootloopnestexperiment.loopnest.subloops_recursive():
            if  loop.filename :
                ccfiles.add( mkpath(loop.filename))


    contents = {}
    for f in ccfiles:
        contents[f.resolve()] = f.open('r').readlines()

    for x in experiment.nestexperiments:
        first = None
        rootloopnestexperiment = x
        while rootloopnestexperiment.derived_from != None:
            rootloopnestexperiment = rootloopnestexperiment.derived_from

        for loop in rootloopnestexperiment.loopnest.subloops_recursive():
            if not loop.isloop:
                continue
            filename = mkpath(loop.filename).resolve()
            line = loop.line-1     # is one-based
            column = loop.column-1 # is one-based
            name = loop.name

            if (first == None) or (first > (line, column)):
                first = (line, column)

            contentlines = contents.get(filename)
            assert contentlines, "Loopnest's file not matched with intput file?!?"

            oldline = contentlines[line]
            # FIXME: if multiple loops per line, ensure that later are replaced first
            newline = oldline[:column] + f"\n#pragma clang loop id({name})\n" + oldline[column:]
            contentlines[line] = newline

        oldline = contentlines[first[0]]
        paramname = param_for_experiment(rootloopnestexperiment) 
        newline = oldline[:first[1]] + '\n#' + paramname+ '\n'  + oldline[first[1]:] 
        contentlines[first[0]] = newline

    # Writeback files in new dir
    newccfiles = []
    for k, content in contents.items():
        filename = outdir / k.name
        createfile(filename, ''.join(content))
        newccfiles.append(filename)
    return newccfiles




def gen_ytopt_problem(filename, outdir: pathlib.Path, max_depth):
    root = read_json(files=filename)

    outdir.mkdir(parents=True,exist_ok=True)
    output = outdir / 'problem.py'

    global params
    conditions = []


    

    newccfiles = prepare_cfiles(root, outdir)



    with output.open('w+') as f:
        f.write(r"""#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, time, json, math
import numpy as np
from autotune import TuningProblem
from autotune.space import *
import ConfigSpace as CS
import ConfigSpace.hyperparameters as CSH
from skopt.space import Real, Integer, Categorical
#Add plopper from src/mctree
#from plopper import *
sys.path.append("../../../src/")
from mctree.plopper import Plopper

cs = CS.ConfigurationSpace(seed=1234)
""")

        """
        enabledif = dict()    

        some_set = []
        experiment_depths = []

        # TODO: One for each nestexperiment
        #X- Adding an extra loopnest parameter
        for experiment in root.derivatives_recursive(max_depth=max_depth-1):
            for cne in experiment.nestexperiments: 
                param = param_for_experiment(cne)
                    
                choices = []
                for c in experiment.derivatives_recursive(max_depth=1):
                    if c is experiment :
                        continue
                    some_set.append((experiment.nestexperiments[0].newpragmas,c.nestexperiments[0].newpragmas))
                    experiment_depths.append((experiment.depth,c.depth))
                    for cne in c.nestexperiments:                
                        addedpragmas = '\n'.join(cne.newpragmas)
                        choice = addedpragmas
                        #x- if experiment.depth < max_depth
                        if experiment.depth < max_depth:
                            cparam = param_for_experiment(cne)
                            choice = f"#{cparam}\n{addedpragmas}"
                            enabledif[cparam] = (param, choice)

                            c = new_cond()
                            conditions.append(f"{c} = CS.EqualsCondition({cparam}, {param}, {pyescape(choice)})")
                            #x- initially outside the if condition
                        choices.append(choice)
                #out = f"{param} = CSH.CategoricalHyperparameter(name='{param}', choices={pylist(choices)}, default_value='')\n"
                f.write(f"{param} = CSH.CategoricalHyperparameter(name='{param}', choices={pylist(choices)}, default_value='')\n") 

        
        enabledif = dict()    

        some_set = []
        experiment_depths = []

        # TODO: One for each nestexperiment
        #X- Adding an extra loopnest parameter
        for experiment in root.derivatives_recursive(max_depth=max_depth):
            for cne in experiment.nestexperiments:
                #if experiment.depth < max_depth:
                param = param_for_experiment(cne)
                    
                choices = []
                for c in experiment.derivatives_recursive(max_depth=1):
                    
                    if c is experiment and c.depth > max_depth :
                        continue
                    some_set.append((experiment.nestexperiments[0].newpragmas,c.nestexperiments[0].newpragmas))
                    experiment_depths.append((experiment.depth,c.depth))
                    for cne in c.nestexperiments:                
                        addedpragmas = '\n'.join(cne.newpragmas)
                        choice = addedpragmas
                        #x- if experiment.depth < max_depth
                        
                        cparam = param_for_experiment(cne)
                        if experiment.depth == max_depth:
                            choice = f"{addedpragmas}"
                        else:
                            choice = f"#{cparam}\n{addedpragmas}"
                        enabledif[cparam] = (param, choice)

                        c = new_cond()
                        conditions.append(f"{c} = CS.EqualsCondition({cparam}, {param}, {pyescape(choice)})")
                        
                        choices.append(choice)
                #out = f"{param} = CSH.CategoricalHyperparameter(name='{param}', choices={pylist(choices)}, default_value='')\n"
                f.write(f"{param} = CSH.CategoricalHyperparameter(name='{param}', choices={pylist(choices)}, default_value='')\n") 
       
        """
        #Counter to keep track of depth reached in the case of a tiemout
        current_depth=0
        enabledif = dict() 
        experiment_depths = []

        for experiment in root.derivatives_recursive(max_depth=max_depth-1):
            for lns in experiment.nestexperiments:
                #if experiment.depth >=max_depth:
                    #continue
                param = param_for_experiment(lns)

                #X- Adding '' as a choice to the first hyperparameter might be unncessary as that's the same as the base kernel/experiment
                choices = ['']
                for child in experiment.derivatives_recursive(max_depth=1):
                    #Removing empty string from P0, as that's the same as the base experiemnt
                    #if child.depth == 0:
                        #choices.remove('')
                    if child is experiment:
                        continue
                    experiment_depths.append((experiment.depth,child.depth))

                    for clns in child.nestexperiments:
                        addedpragmas = '\n'.join(clns.newpragmas)
                        choice = addedpragmas

                        if child.depth < max_depth:
                            cparam = param_for_experiment(clns)
                            choice = f"#{cparam}\n{addedpragmas}"
                            enabledif[cparam]=(param,choice)
                            c = new_cond()
                            conditions.append(f"{c} = CS.EqualsCondition({cparam}, {param}, {pyescape(choice)})")
                            current_depth +=1
                        else: #child.depth == max_depth:
                            cparam = param_for_experiment(clns)
                            choice = f"{addedpragmas}"
                            enabledif[cparam]=(param,choice)
                            params.remove(cparam)
                            current_depth +=1
                    
                    choices.append(choice)
                #empty_string = pyescape("")
                f.write(f"{param} = CSH.CategoricalHyperparameter(name='{param}', choices={pylist(choices)}, default_value=None)\n")
        
        counter_num_experiments = 0
        exp_depth = []
        for experiment in root.derivatives_recursive(max_depth=max_depth):
            exp_depth.append(experiment.depth)
            param = None
            assert len(experiment.nestexperiments)==1
            for cne in experiment.nestexperiments:
                param = param_for_experiment(cne)
                counter_num_experiments +=1

                eparams = cne.newparams
                for ep in eparams:
                    #X- Change it in mctree.Transformers?
                    #Convert ep.choice from int to String for ytopt problem.py
                    ep_choices = [str(epc) for epc in ep.choices]
                    ep_choices0 = pyescape(ep_choices[0])
                    #out2 = f"{ep.name} = CSH.CategoricalHyperparameter(name='{ep.name}', choices={ep.choices}, default_value={pyescape(ep.choices[0])})\n"
                    f.write(f"{ep.name} = CSH.CategoricalHyperparameter(name='{ep.name}', choices={ep_choices}, default_value={ep_choices0})\n") 
                    params.append(ep.name)

                    parentp,parentv = enabledif.get(param)

                    c = new_cond()
                    conditions.append(f"{c} = CS.EqualsCondition({ep.name}, {parentp}, {pyescape(parentv)})")
        

        f.write(f"cs.add_hyperparameters([{', '.join(params)}])\n")
        f.write("\n")

        for c in conditions:
            f.write(c)
            f.write('\n')
        f.write(f"cs.add_conditions([{', '.join(condnames)}])\n")

        f.write("\n")
        #f.write(f'sourcefile = {pyescape(str(newccfiles))}\n') # TODO: More than one file
        f.write(f'sourcefile = {pyescape(str(newccfiles[0]))}\n') # TODO: More than one file

        f.write(r"""
input_space = cs
output_space = Space([Real(0.0, inf, name='time')])

dir_path = os.path.dirname(os.path.realpath(sourcefile))
obj = Plopper(sourcefile,dir_path)""")
        f.write(f"\n#Stats that might be useful\n")
        f.write(f"current_depth_reached = {current_depth}\n")
        f.write(f"counter_num_experiments = {counter_num_experiments}\n")
        f.write(r"""
def myobj(point: dict):
    def plopper_func(x):
        x = np.asarray_chkfinite(x)  # ValueError if any NaN or Inf
        value = list(point.values())
        print('VALUES:', point)
        params = {k.upper(): v for k, v in point.items()}
        result = obj.findRuntime(value, params)
        return result
    x = np.array(list(point.values())) #len(point) = 13 or 26
    results = plopper_func(x)
    print('OUTPUT:%f',results)

    return results

Problem = TuningProblem(
    task_space=None,
    input_space=input_space,
    output_space=output_space,
    objective=myobj,
    constraints=None,
    model=None)
""")

    return current_depth, counter_num_experiments







