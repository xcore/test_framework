import random
import xmos.test.generator as generator

random.seed(1)

if __name__ == "__main__":
  seq = generator.Sequence([
          generator.Command("+", repeat=2),
          generator.Choice([
            generator.Command("A", weight=10),
            generator.Command("B", weight=1)
          ], repeat=10),
          generator.Command("*")], order_rand=True, repeat=10)

  for i in seq:
      print i

