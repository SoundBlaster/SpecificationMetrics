class Helper:
    def __getattr__(self, name):
        return None


def make_helper():
    def __getattr__(name):
        return None

    return object()
