
class ParameterCounter:
    def __init__(self):
        self.prevparamid = -1

    def clone(self):
        result = ParameterCounter()
        result.prevparamid=self.prevparamid
        return result
    
    def nextParamID(self):
        self.prevparamid +=1
        return self.prevparamid

global p 
p= ParameterCounter()