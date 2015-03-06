# We define a "logger" wich stuffs messages onto a queue
# TODO: Fix this in a proper way
class Logger(object):
    def __init__(self, log_queue):
        global global_logger_queue
        global_logger_queue = log_queue

    def __getattribute__(self, name):
        def put_on_queue(*args, **kwargs):
            tmp = (name, args)
            global_logger_queue.put(tmp)
        return put_on_queue

