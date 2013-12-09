import random

class Object(object):
  def __init__(self, items, weight=1, repeat=1):
    self.items = items
    self.weight = weight
    self.repeat = repeat
    self.current_repeat = 0

  def __iter__(self):
    return self

  def reset(self):
    self.current_repeat = 0
    self.reset_items()

  def reset_items(self):
    for item in self.items:
      item.reset()

class Command(Object):
  def __init__(self, command, weight=1, repeat=1):
    super(Command, self).__init__([], weight=weight, repeat=repeat)
    self.command = command

  def next(self):
    if self.current_repeat < self.repeat:
      self.current_repeat += 1
      return self.command
    raise StopIteration


class Sequence(Object):
  def __init__(self, items, weight=1, repeat=1, order_rand=False):
    super(Sequence, self).__init__(items, weight=weight, repeat=repeat)
    self.order_rand = order_rand
    self.current_index = 0
    self.start_iteration()

  def next(self):
    while self.current_repeat < self.repeat and self.current_index < len(self.items):
      try:
        return self.items[self.indexes[self.current_index]].next()
      except StopIteration:
        self.current_index += 1
        if self.current_index == len(self.items):
          self.current_index = 0
          self.current_repeat += 1
          self.start_iteration()

    raise StopIteration

  def reset(self):
    super(Sequence, self).reset()
    self.current_index = 0

  def start_iteration(self):
    """ Set of indexes to allow the order_rand to guarantee that all entries are used only once
    """
    self.indexes = range(len(self.items))
    if self.order_rand:
      random.shuffle(self.indexes)

    # In order to be able to iterate multiple times, need to clear the repeat count
    self.reset_items()


class Choice(Object):
  def __init__(self, items, weight=1, repeat=1):
    super(Choice, self).__init__(items, weight=weight, repeat=repeat)
    self.total_weight = sum(item.weight for item in items)
    self.start_iteration()

  def next(self):
    while self.current_repeat < self.repeat:
      try:
        return self.choice.next()
      except StopIteration:
        self.current_repeat += 1
        self.start_iteration()

    raise StopIteration

  def start_iteration(self):
    """ On each repeat need to choose randomly from the set of options.
    """
    self.choice = None

    rand_value = random.randint(0, self.total_weight - 1)
    for i in self.items:
      if rand_value < i.weight:
        self.choice = i
        break
      rand_value -= i.weight

    assert self.choice

    # In order to be able to iterate multiple times, need to clear the repeat count
    self.reset_items()


def json_hooks(dct):
  if 'sequence' in dct:
    order_rand = dct.get('order_rand', False)
    repeat = dct.get('repeat', 1)
    weight = dct.get('weight', 1)
    return Sequence(dct['sequence'], weight=weight, order_rand=order_rand, repeat=repeat)

  elif 'choice' in dct:
    repeat = dct.get('repeat', 1)
    weight = dct.get('weight', 1)
    return Choice(dct['choice'], weight=weight, repeat=repeat)

  elif 'command' in dct:
    repeat = dct.get('repeat', 1)
    weight = dct.get('weight', 1)
    return Command(dct['command'], weight=weight, repeat=repeat)
  
  return dct

