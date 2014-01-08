import os

""" Spawns a new process on a remote machine using ssh.

 The function takes arguments similar to the spawnProcess method
 of the reactor object in twistd. The extra is_windows argument should
 be used to indicate whether the remote machine is a windows machine or not.
"""
def spawnRemoteProcess(reactor, user, host, protocol, executable, args, cwd,
                       is_windows = False):
    if is_windows:
        args = ['ssh','-q','-n',user + "@" + host] + ['cmd /c "cd ' + cwd + ' && ' + ' '.join(args) + '"']
        reactor.spawnProcess(protocol, 'ssh', args, os.environ)
    else:
        reactor.spawnProcess(protocol, 'ssh', ['ssh','-q','-n',user + "@" + host] + ['cd ' + cwd + ';' + ' '.join(args)], os.environ)


