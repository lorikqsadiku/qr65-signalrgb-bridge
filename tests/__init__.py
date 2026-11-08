import logging

# Keep test output clean: the code under test logs expected warnings on its failure paths.
logging.getLogger("qr65").addHandler(logging.NullHandler())
logging.getLogger("qr65").propagate = False
