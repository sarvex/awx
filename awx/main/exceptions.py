# Copyright (c) 2018 Ansible by Red Hat
# All Rights Reserved.


class _AwxTaskError:
    def build_exception(self, task, message=None):
        if message is None:
            message = f"Execution error running {task.log_format}"
        e = Exception(message)
        e.task = task
        e.is_awx_task_error = True
        return e

    def TaskCancel(self, task, rc):
        """Canceled flag caused run_pexpect to kill the job run"""
        message = f"{task.log_format} was canceled (rc={rc})"
        e = self.build_exception(task, message)
        e.rc = rc
        e.awx_task_error_type = "TaskCancel"
        return e

    def TaskError(self, task, rc):
        """Userspace error (non-zero exit code) in run_pexpect subprocess"""
        message = f"{task.log_format} encountered an error (rc={rc}), please see task stdout for details."
        e = self.build_exception(task, message)
        e.rc = rc
        e.awx_task_error_type = "TaskError"
        return e


AwxTaskError = _AwxTaskError()


class PostRunError(Exception):
    def __init__(self, msg, status='failed', tb=''):
        self.status = status
        self.tb = tb
        super(PostRunError, self).__init__(msg)


class ReceptorNodeNotFound(RuntimeError):
    pass
