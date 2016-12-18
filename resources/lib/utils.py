__author__ = 'thesebas'
import time

class Memoize:
    def __init__(self, func):
        self.func = func
        self.func_name = func.func_name
        self.cache = {}

    def __call__(self, *args):
        if repr(args) not in self.cache:
            print "MEMOIZE:(%s) real" % (self.func.func_name,)
            self.cache[repr(args)] = self.func(*args)
        else:
            print "MEMOIZE(%s) from cache" % (self.func.func_name,)
            pass

        return self.cache[repr(args)]


class MeasureTime:
    def __init__(self, func):
        self.func = func

    def __call__(self, *args):
        print "MeasureTime: %s start" % (self.func.func_name, )
        start = time.time()
        result = self.func(*args)
        print "MeasureTime: %s end: %f" % (self.func.func_name, time.time() - start)

        return result
