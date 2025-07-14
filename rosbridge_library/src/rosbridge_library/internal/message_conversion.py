#!/usr/bin/env python3
# Software License Agreement (BSD License)
#
# Copyright (c) 2012, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of Willow Garage, Inc. nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import array
import math
import re
from base64 import standard_b64decode, standard_b64encode

import numpy as np
from rcl_interfaces.msg import Parameter
from rclpy.clock import ROSClock
from rclpy.time import Duration, Time
from rosbridge_library.internal import ros_loader
from rosbridge_library.util import bson

try:
    import rospy
except ImportError:
    rospy = None

type_map = {
    "bool": ["bool", "boolean"],
    "int": [
        "int8",
        "octet",
        "uint8",
        "char",
        "int16",
        "uint16",
        "int32",
        "uint32",
        "int64",
        "uint64",
    ],
    "float": ["float32", "float64", "double", "float"],
    "str": ["string"],
}
primitive_types = [bool, int, float]

list_types = [list, tuple, np.ndarray, array.array]
ros_time_types = ["builtin_interfaces/Time", "builtin_interfaces/Duration"]
ros_primitive_types = [
    "bool",
    "boolean",
    "octet",
    "char",
    "int8",
    "uint8",
    "int16",
    "uint16",
    "int32",
    "uint32",
    "int64",
    "uint64",
    "float32",
    "float64",
    "float",
    "double",
    "string",
]
ros_header_types = ["Header", "std_msgs/Header", "roslib/Header"]
ros_binary_types = ["uint8[]", "char[]", "sequence<uint8>", "sequence<char>"]
# Remove the list type wrapper, and length specifier, from rostypes i.e. sequence<double, 3>
list_tokens = re.compile(r"<(.+?)(, \d+)?>")
bounded_array_tokens = re.compile(r"(.+)\[.*\]")
ros_binary_types_list_braces = [
    ("uint8[]", re.compile(r"uint8\[[^\]]*\]")),
    ("char[]", re.compile(r"char\[[^\]]*\]")),
]

binary_encoder = None
binary_encoder_type = "default"
bson_only_mode = False


# TODO(@jubeira): configure module with a node handle.
# The original code doesn't seem to actually use these parameters.
def configure(node_handle=None):
    global binary_encoder, binary_encoder_type, bson_only_mode

    if node_handle is not None:
        binary_encoder_type = node_handle.get_parameter_or(
            "binary_encoder", Parameter("", value="default")
        ).value
        bson_only_mode = node_handle.get_parameter_or(
            "bson_only_mode", Parameter("", value=False)
        ).value

    # Always reconfigure binary_encoder based on current settings
    if binary_encoder_type == "bson" or bson_only_mode:
        binary_encoder = bson.Binary
    elif binary_encoder_type == "default" or binary_encoder_type == "b64":
        binary_encoder = standard_b64encode
    else:
        print("Unknown encoder type '%s'" % binary_encoder_type)
        exit(0)
    


def get_encoder():
    # Legacy function - now uses binary_encoder_type only
    global binary_encoder, binary_encoder_type
    
    # Configure binary_encoder based on type setting
    if binary_encoder_type == "bson":
        binary_encoder = bson.Binary
    elif binary_encoder_type == "default" or binary_encoder_type == "b64":
        binary_encoder = standard_b64encode
    else:
        binary_encoder = standard_b64encode  # fallback
    
    return binary_encoder


class InvalidMessageException(Exception):
    def __init__(self, inst):
        Exception.__init__(
            self,
            "Unable to extract message values from %s instance" % type(inst).__name__,
        )


class NonexistentFieldException(Exception):
    def __init__(self, basetype, fields):
        Exception.__init__(
            self,
            "Message type {} does not have a field {}".format(basetype, ".".join(fields)),
        )


class FieldTypeMismatchException(Exception):
    def __init__(self, roottype, fields, expected_type, found_type):
        if roottype == expected_type:
            Exception.__init__(
                self,
                f"Expected a JSON object for type {roottype} but received a {found_type}",
            )
        else:
            Exception.__init__(
                self,
                "{} message requires a {} for field {}, but got a {}".format(
                    roottype, expected_type, ".".join(fields), found_type
                ),
            )


def extract_values(inst, bson_only_mode=False):
    rostype = msg_instance_type_repr(inst)
    
    if rostype is None:
        raise InvalidMessageException(inst=inst)
    return _from_inst(inst, rostype, bson_only_mode)


def extract_json_values(inst):
    """Extract message values for JSON encoding (with Base64 for binary data)."""
    return extract_values(inst, bson_only_mode=False)


def extract_bson_values(inst):
    """Extract message values for BSON encoding (with Binary objects for efficiency)."""
    return extract_values(inst, bson_only_mode=True)


def populate_instance(msg, inst, clock=ROSClock()):
    """Returns an instance of the provided class, with its fields populated
    according to the values in msg"""
    inst_type = msg_instance_type_repr(inst)

    return _to_inst(msg, inst_type, inst_type, clock, inst)


def msg_instance_type_repr(msg_inst):
    """Returns a string representation of a ROS2 message type from a message instance"""
    # Message representation: '{package}.msg.{message_name}({fields})'.
    # A representation like '_type' member in ROS1 messages is needed: '{package}/{message_name}'.
    # E.g: 'std_msgs/Header'
    msg_type = type(msg_inst)
    if msg_type in primitive_types or msg_type in list_types:
        return str(type(msg_inst))
    inst_repr = str(msg_inst).split(".")
    return "{}/{}".format(inst_repr[0], inst_repr[2].split("(")[0])


def msg_class_type_repr(msg_class):
    """Returns a string representation of a ROS2 message type from a class representation."""
    # The string representation of the class is <class '{package}.msg._{message}.{Message}'>
    # (e.g. <class 'std_msgs.msg._string.String'>).
    # This has to be converted to {package}/msg/{Message} (e.g. std_msgs/msg/String).
    class_repr = str(msg_class).split("'")[1].split(".")
    return f"{class_repr[0]}/{class_repr[1]}/{class_repr[3]}"


def _from_inst(inst, rostype, bson_only_mode=False):
    # Special case for uint8[], we encode the string
    for binary_type, expression in ros_binary_types_list_braces:
        match_result = expression.sub(binary_type, rostype)
        
        if match_result in ros_binary_types:
            # Use passed parameter instead of global variable for better control
            if bson_only_mode:
                # Zero-copy optimized BSON Binary creation
                return _create_zero_copy_binary(inst)
            else:
                # For JSON mode, use base64 encoding
                encoded = get_encoder()(inst)
                return encoded.decode("ascii")

    # Check for time or duration
    if rostype in ros_time_types:
        return {"sec": inst.sec, "nanosec": inst.nanosec}

    # bson_only_mode is now passed as parameter - no need for global fallback
    # Check for primitive types
    if rostype in ros_primitive_types:
        # JSON does not support Inf and NaN. They are mapped to None and encoded as null
        if (not bson_only_mode) and (rostype in type_map.get("float")):
            if math.isnan(inst) or math.isinf(inst):
                return None

        # JSON does not support byte array. They are converted to int
        if (not bson_only_mode) and (rostype == "octet"):
            return int.from_bytes(inst, "little")

        return inst

    # Check if it's a list or tuple
    if type(inst) in list_types:
        return _from_list_inst(inst, rostype, bson_only_mode)

    # Assume it's otherwise a full ros msg object
    return _from_object_inst(inst, rostype, bson_only_mode)


def _from_list_inst(inst, rostype, bson_only_mode=False):
    # Can duck out early if the list is empty
    if len(inst) == 0:
        return []

    # Remove the list indicators from the rostype
    try:
        rostype = re.search(list_tokens, rostype).group(1)
    except AttributeError:
        rostype = re.search(bounded_array_tokens, rostype).group(1)

    # Shortcut for primitives
    if rostype in ros_primitive_types:
        # Convert to Built-in integer types to dump as JSON
        if isinstance(inst, np.ndarray) and (
            rostype in type_map.get("int") or rostype in type_map.get("float")
        ):
            return inst.tolist()

        if rostype not in type_map.get("float"):
            return list(inst)

    # Call to _to_inst for every element of the list
    return [_from_inst(x, rostype, bson_only_mode) for x in inst]


def _from_object_inst(inst, rostype, bson_only_mode=False):
    # Zero-copy optimization for BSON mode
    if bson_only_mode:
        return _from_object_inst_zero_copy(inst, rostype)
    
    # Standard implementation for JSON mode
    return _from_object_inst_standard(inst, rostype, bson_only_mode)


def _from_object_inst_zero_copy(inst, rostype):
    """Zero-copy optimized message conversion for BSON mode."""
    # Pre-allocate result dictionary
    fields_and_types = inst.get_fields_and_field_types()
    msg = {}
    
    # Batch field access to minimize getattr() calls
    for field_name, field_rostype in fields_and_types.items():
        field_inst = getattr(inst, field_name)
        
        # Zero-copy optimization for binary data
        if _is_binary_field(field_rostype):
            msg[field_name] = _create_zero_copy_binary(field_inst)
        else:
            msg[field_name] = _from_inst(field_inst, field_rostype, bson_only_mode=True)
    
    return msg


def _from_object_inst_standard(inst, rostype, bson_only_mode=False):
    """Standard message conversion implementation."""
    # Create an empty dict then populate with values from the inst
    msg = {}
    # Equivalent for zip(inst.__slots__, inst._slot_types) in ROS1:
    for field_name, field_rostype in inst.get_fields_and_field_types().items():
        field_inst = getattr(inst, field_name)
        msg[field_name] = _from_inst(field_inst, field_rostype, bson_only_mode)
    return msg


def _is_binary_field(field_rostype):
    """Check if field type represents binary data suitable for zero-copy optimization."""
    # Check against ros_binary_types patterns
    for binary_type, expression in ros_binary_types_list_braces:
        match_result = expression.sub(binary_type, field_rostype)
        if match_result in ros_binary_types:
            return True
    return False


def _create_zero_copy_binary(field_inst):
    """Create BSON Binary with zero-copy optimization."""
    from rosbridge_library.util import bson
    
    # ROS2 array.array optimization (most common case for PointCloud2)
    if hasattr(field_inst, 'tobytes'):
        # array.array has efficient tobytes() method - zero-copy
        try:
            return bson.Binary(field_inst.tobytes())
        except (TypeError, AttributeError):
            pass
    
    # Direct memory view optimization for NumPy arrays
    if hasattr(field_inst, '__array_interface__'):
        # NumPy array or similar - use memoryview for zero-copy
        try:
            memory_view = memoryview(field_inst)
            return bson.Binary(memory_view)
        except (TypeError, BufferError):
            pass
    
    # Python buffer protocol support
    try:
        # Try to create memoryview directly
        memory_view = memoryview(field_inst)
        return bson.Binary(memory_view)
    except (TypeError, ValueError):
        pass
    
    # Bytes-like objects optimization
    if isinstance(field_inst, (bytes, bytearray)):
        # Direct bytes - already optimal
        return bson.Binary(field_inst)
    
    # List/tuple of integers (fallback for uint8 arrays)
    if isinstance(field_inst, (list, tuple)) and field_inst:
        if all(isinstance(x, int) and 0 <= x <= 255 for x in field_inst[:10]):  # Sample check
            # Convert to bytes efficiently
            try:
                byte_data = bytes(field_inst)
                return bson.Binary(byte_data)
            except (ValueError, TypeError):
                pass
    
    # Fallback to standard BSON Binary creation
    return bson.Binary(field_inst)


def _to_inst(msg, rostype, roottype, clock=ROSClock(), inst=None, stack=[]):
    # Check if it's uint8[], and if it's a string, try to b64decode
    for binary_type, expression in ros_binary_types_list_braces:
        if expression.sub(binary_type, rostype) in ros_binary_types:
            return _to_binary_inst(msg)

    # Check the type for time or rostime
    if rostype in ros_time_types:
        return _to_time_inst(msg, rostype, clock, inst)

    # Check to see whether this is a primitive type
    if rostype in ros_primitive_types:
        return _to_primitive_inst(msg, rostype, roottype, stack)

    # Check whether we're dealing with a list type
    if inst is not None and type(inst) in list_types:
        return _to_list_inst(msg, rostype, roottype, clock, inst, stack)

    # Otherwise, the type has to be a full ros msg type, so msg must be a dict
    if inst is None:
        inst = ros_loader.get_message_instance(rostype)

    return _to_object_inst(msg, rostype, roottype, clock, inst, stack)


def _to_binary_inst(msg):
    global bson_only_mode
    
    # Handle BSON Binary objects (only in BSON mode)
    if bson_only_mode and hasattr(msg, '__class__') and 'Binary' in str(type(msg)):
        # Extract bytes from BSON Binary object
        data = array.array("B")
        data.frombytes(bytes(msg))
        return data
    if isinstance(msg, str):
        return list(standard_b64decode(msg))
    if isinstance(msg, list):
        return msg
    if isinstance(msg, bytes):
        # Using the frombytes() method with a memoryview of the data allows for zero copying of data thanks to Python's buffer protocol (HUGE time-saver for large arrays)
        data = array.array("B")
        data.frombytes(memoryview(msg))
        return data
    return bytes(bytearray(msg))


def _to_time_inst(msg, rostype, clock, inst=None):
    # Create an instance if we haven't been provided with one

    if rostype == "builtin_interfaces/Time" and msg == "now":
        return clock.now().to_msg()

    if inst is None:
        if rostype == "builtin_interfaces/Time":
            inst = Time().to_msg()
        elif rostype == "builtin_interfaces/Duration":
            inst = Duration().to_msg()
        else:
            return None

    # Copy across the fields, try ROS1 and ROS2 fieldnames
    for field in ["sec", "secs"]:
        if field in msg:
            setattr(inst, "sec", msg[field])
            break
    for field in ["nanosec", "nsecs"]:
        if field in msg:
            setattr(inst, "nanosec", msg[field])
            break

    return inst


def _to_primitive_inst(msg, rostype, roottype, stack):
    # Typecheck the msg
    if isinstance(msg, int) and rostype in type_map["float"]:
        # probably wrong parsing,
        # fix that by casting the int to the expected float
        msg = float(msg)

    # Convert to byte
    if rostype == "octet" and isinstance(msg, int):
        return bytes([msg])

    msgtype = type(msg)
    if msgtype in primitive_types and rostype in type_map[msgtype.__name__]:
        return msg
    elif isinstance(msg, str) and rostype in type_map[msgtype.__name__]:
        return msg
    raise FieldTypeMismatchException(roottype, stack, rostype, msgtype)


def _to_list_inst(msg, rostype, roottype, clock, inst, stack):
    # Typecheck the msg
    if type(msg) not in list_types:
        raise FieldTypeMismatchException(roottype, stack, rostype, type(msg))

    # Can duck out early if the list is empty
    if len(msg) == 0:
        return []

    # Special mappings for numeric types https://design.ros2.org/articles/idl_interface_definition.html
    if isinstance(inst, array.array):
        del inst[:]
        inst.extend(msg)  # accepts both ints and floats which may come from json
        return inst
    if isinstance(inst, np.ndarray):
        inst[:] = msg  # accepts both ints and floats which may come from json
        return inst

    # Remove the list indicators from the rostype
    try:
        rostype = re.search(list_tokens, rostype).group(1)
    except AttributeError:
        rostype = re.search(bounded_array_tokens, rostype).group(1)

    # Call to _to_inst for every element of the list
    return [_to_inst(x, rostype, roottype, clock, None, stack) for x in msg]


def _to_object_inst(msg, rostype, roottype, clock, inst, stack):

    # Typecheck the msg
    if not isinstance(msg, dict):
        raise FieldTypeMismatchException(roottype, stack, rostype, type(msg))

    # Substitute the correct time if we're an std_msgs/Header
    if rostype in ros_header_types:
        inst.stamp = clock.now().to_msg()

    inst_fields = inst.get_fields_and_field_types()
    for field_name in msg:
        # Add this field to the field stack
        field_stack = stack + [field_name]

        # Raise an exception if the msg contains a bad field
        if field_name not in inst_fields:
            raise NonexistentFieldException(roottype, field_stack)

        field_rostype = inst_fields[field_name]
        field_inst = getattr(inst, field_name)

        field_value = _to_inst(
            msg[field_name], field_rostype, roottype, clock, field_inst, field_stack
        )

        setattr(inst, field_name, field_value)

    return inst
