#!python
"""This module allows to create temporary mmapped arrays."""

# builtin
import atexit
import logging
import os
import shutil
import tempfile

# external
import mmap
import numpy as np


def make_temp_dir(prefix: str = "temp_mmap_") -> tuple:
    """Make a temporary directory.

    Parameters
    ----------
    prefix : str
        The prefix for the temporary directory.

    Returns
    -------
    tuple
        The temporary directory and its name.
    """
    _temp_dir = tempfile.TemporaryDirectory(prefix=prefix)
    temp_dir_name = _temp_dir.name
    return _temp_dir, temp_dir_name


_TEMP_DIR, TEMP_DIR_NAME = make_temp_dir()
ARRAYS = {}
CLOSED = False
ALLOW_NDARRAY_SUBCLASS = True

logging.warning(
    f"WARNING: Temp mmap arrays are written to {TEMP_DIR_NAME}. "
    "Cleanup of this folder is OS dependant, "
    "and might need to be triggered manually! "
    f"Current space: {shutil.disk_usage(TEMP_DIR_NAME)[-1]}"
)


def empty(shape: tuple, dtype: np.dtype) -> np.ndarray:
    """Create a writable temporary mmapped array.

    Parameters
    ----------
    shape : tuple
        A tuple with the shape of the array.
    dtype : type
        The np.dtype of the array.

    Returns
    -------
    type
        A writable temporary mmapped array.
    """
    element_count = np.prod(shape)
    if element_count <= 0:
        raise ValueError(
            f"Shape {shape} has an invalid element count of {element_count}"
        )
    *other, free_space = shutil.disk_usage(TEMP_DIR_NAME)
    required_space = element_count * np.dtype(dtype).itemsize
    if free_space < required_space:
        raise IOError(
            f"Cannot create array of size {required_space} "
            f"(available space on {TEMP_DIR_NAME} is {free_space})."
        )
    temp_file_name = os.path.join(
        TEMP_DIR_NAME,
        f"temp_mmap_{np.random.randint(2**31)}{np.random.randint(2**31)}.bin"
    )
    with open(temp_file_name, "wb") as binfile:
        binfile.seek(required_space - 1)
        binfile.write(b"0")
        offset = 0
    with open(temp_file_name, "rb+") as raw_hdf_file:
        _mmap_obj = mmap.mmap(
            raw_hdf_file.fileno(),
            0,
            access=mmap.ACCESS_WRITE
        )
        _array = np.frombuffer(
            _mmap_obj,
            dtype=dtype,
            count=element_count,
            offset=offset
        ).reshape(shape)
        if ALLOW_NDARRAY_SUBCLASS:
            _array = TempMMapArray(_array, temp_file_name)
        ARRAYS[temp_file_name] = (_array, _mmap_obj)
        return _array


def zeros(shape: tuple, dtype: np.dtype) -> np.ndarray:
    """Create a writable temporary mmapped array filled with zeros.

    Parameters
    ----------
    shape : tuple
        A tuple with the shape of the array.
    dtype : type
        The np.dtype of the array.

    Returns
    -------
    type
        A writable temporary mmapped array filled with zeros.
    """
    _array = empty(shape, dtype)
    _array[:] = 0
    return _array


def ones(shape: tuple, dtype: np.dtype) -> np.ndarray:
    """Create a writable temporary mmapped array filled with ones.

    Parameters
    ----------
    shape : tuple
        A tuple with the shape of the array.
    dtype : type
        The np.dtype of the array.

    Returns
    -------
    type
        A writable temporary mmapped array filled with ones.
    """
    _array = empty(shape, dtype)
    _array[:] = 1
    return _array


def clone(array: np.ndarray) -> np.ndarray:
    """Create a writable temporary mmapped array copy.

    Parameters
    ----------
    array : np.ndarray
        An array that needs to be copied.

    Returns
    -------
    np.ndarray
        A writable temporary mmapped array that is a copy of array.

    Raises
    ------
    ExceptionName
        Why the exception is raised.

    """
    _array = empty(array.shape, array.dtype)
    _array[:] = array
    return _array


@atexit.register
def atexit_clear() -> str:
    """Reset the temporary folder containing temp mmapped arrays.

    WARNING: All existing temp mmapp arrays will be unusable!

    Returns
    -------
    str
        The name of the new temporary folder.
    """
    global CLOSED
    CLOSED = True
    clear()


def clear() -> str:
    """Reset the temporary folder containing temp mmapped arrays.

    WARNING: All existing temp mmapp arrays will be unusable!

    Returns
    -------
    str
        The name of the new temporary folder.
    """
    global _TEMP_DIR
    global TEMP_DIR_NAME
    global ARRAYS
    global CLOSED
    if not CLOSED:
        logging.warning(
            f"Folder {TEMP_DIR_NAME} with temp mmap arrays is being deleted. "
            "All existing temp mmapp arrays will be unusable!"
        )
        CLOSED = True
    for _array in ARRAYS.values():
        _array[1].close()
    del _TEMP_DIR
    _TEMP_DIR, TEMP_DIR_NAME = make_temp_dir()
    ARRAYS = {}
    return TEMP_DIR_NAME


class TempMMapArray(np.ndarray):
    """A np.ndarray with path attribute for a temporary mmapped buffer."""

    def __new__(cls, input_array, _path):
        obj = np.asarray(input_array).view(cls)
        obj._path = _path
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        self._path = getattr(obj, '_path', None)

    @property
    def path(self):
        return self._path
