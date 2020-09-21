from typing import List


def split_fixed_length(s: str, lengths: List[int], strip: bool = True) -> List[str]:
    """
    Take a string and split it into fixed-length chunks

    Args:
        s (str): The string
        lengths (List[int]): 
            Ordered list of each fixed-length chunk size
            sum(lengths) <= len(s)
            if sum(lengths) < len(s), the last element 
            returned will be the remainder of the string
        strip (bool, optional): 
            Do I strip whitespace for each parsed element? 
            Defaults to True.
    """
    # fmt: off
    assert sum(lengths) <= len(s), \
        'Sum of each chunk length is greater than the length of the input string'
    # fmt: on

    def get_value(v):
        return v.strip() if strip else v

    start_idx = 0
    for length in lengths:
        end_idx = start_idx + length
        yield get_value(s[start_idx:end_idx])
        start_idx = end_idx

    if end_idx < len(s):
        yield get_value(s[end_idx:])
