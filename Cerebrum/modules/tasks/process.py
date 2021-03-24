import datetime
import logging

from Cerebrum.database.ctx import savepoint
from Cerebrum.utils import backoff
from Cerebrum.utils.date import now
from Cerebrum.modules.tasks import task_models
from Cerebrum.modules.tasks import task_queue

logger = logging.getLogger(__name__)


def copy_task(task):
    return task_models.Task.from_dict(task.to_dict())


delay_on_error = backoff.Backoff(
    backoff.Exponential(2),
    backoff.Factor(datetime.timedelta(hours=1) / 16),
    backoff.Truncate(datetime.timedelta(hours=12)),
)


class QueueHandler(object):
    """ Processing rules and task implementation for a given set of queues. """

    # queue for adding regular tasks
    queue = 'example'

    # queue for adding tasks with a future nbf date
    # defaults to *queue*
    nbf_queue = None

    # queue for re-queueing failed tasks
    # defaults to the same queue as regular tasks
    retry_queue = None

    # delay queue for tasks if we discover a future date during handling
    # defaults to the same queue as regular tasks
    delay_queue = None

    # extra queue for tasks that were added manually
    manual_queue = None

    # when to give up on a task
    max_attempts = 20

    @property
    def all_queues(self):
        return tuple(
            q for q in (self.queue, self.nbf_queue, self.retry_queue,
                        self.delay_queue, self.manual_queue)
            if q)

    def get_retry_task(self, task, error):
        """ Create a retry task if task fails. """
        retry = copy_task(task)
        retry.queue = self.retry_queue or self.queue
        retry.attempts = task.attempts + 1
        retry.nbf = now() + delay_on_error(task.attempts + 1)
        retry.reason = 'retry: failed_at={} error={}'.format(now(), error)
        return retry

    def handle_task(self, db, dryrun, task):
        raise NotImplementedError('abstract method')

    def __call__(self, db, dryrun, task):
        logger.debug('processing task: %r', task.to_dict())
        new_task = None
        try:
            with savepoint(db, dryrun):
                new_task = self.handle_task(db, dryrun, task)
            logger.info('processed task: %r', task)
        except Exception as e:
            logger.warning('failed task: %r', task, exc_info=True)
            new_task = self.get_retry_task(task, e)

        if new_task and task_queue.TaskQueue(db).push(new_task):
            logger.info('queued task: %r', new_task)
