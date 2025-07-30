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
verbose_debug_mode = False


# TODO(@jubeira): configure module with a node handle.
# The original code doesn't seem to actually use these parameters.
def configure(node_handle=None):
    global binary_encoder, binary_encoder_type, bson_only_mode, verbose_debug_mode

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
    import time
    start_time = time.time()
    
    # Use ERROR level for guaranteed visibility
    import logging
    logger = logging.getLogger(__name__)
    
    # Measure msg_instance_type_repr processing time
    type_repr_start = time.time()
    rostype = msg_instance_type_repr(inst)
    type_repr_elapsed = time.time() - type_repr_start
    
    if verbose_debug_mode and rostype and rostype.startswith("sensor_msgs"):
        logger.debug(f"[BSON_DEBUG] extract_values ENTRY: {rostype}, bson_only_mode={bson_only_mode}")
        logger.debug(f"[BSON_DEBUG] msg_instance_type_repr() OPTIMIZED took {type_repr_elapsed*1000:.3f}ms")
    
    if rostype is None:
        raise InvalidMessageException(inst=inst)
    
    # Log before _from_inst call
    from_inst_start = time.time()
    elapsed_before_from_inst = from_inst_start - start_time
    if verbose_debug_mode:
        logger.debug(f"[BSON_DEBUG] About to call _from_inst for {rostype}")
        logger.debug(f"[BSON_DEBUG] Time before _from_inst call: {elapsed_before_from_inst*1000:.3f}ms")
    
    result = _from_inst(inst, rostype, bson_only_mode)
    
    from_inst_elapsed = time.time() - from_inst_start
    if verbose_debug_mode:
        logger.debug(f"[BSON_DEBUG] _from_inst completed in {from_inst_elapsed*1000:.3f}ms")
    
    # Log after _from_inst - check for post-processing bottleneck
    post_process_start = time.time()
    if verbose_debug_mode:
        logger.debug(f"[BSON_DEBUG] Starting post-processing after _from_inst")
    
    # Log result characteristics for bottleneck analysis
    if isinstance(result, dict):
        result_size = len(result)
        if verbose_debug_mode:
            logger.debug(f"[BSON_DEBUG] Result dict has {result_size} keys")
        
        # Check for large data fields that might cause slowdown
        large_fields = []
        for key, value in result.items():
            if hasattr(value, '__len__') and len(value) > 10000:
                large_fields.append(f"{key}({len(value)})")
        
        if large_fields:
            if verbose_debug_mode:
                logger.debug(f"[BSON_DEBUG] Large fields detected: {large_fields}")
    
    post_process_elapsed = time.time() - post_process_start
    if verbose_debug_mode:
        logger.debug(f"[BSON_DEBUG] Post-processing completed in {post_process_elapsed*1000:.3f}ms")
    
    # Check for memory operations that might be causing the bottleneck
    memory_check_start = time.time()
    if verbose_debug_mode:
        logger.debug(f"[BSON_DEBUG] Starting memory operations check")
    
    # Check result serialization time
    try:
        import sys
        result_mem_size = sys.getsizeof(result)
        if verbose_debug_mode:
            logger.debug(f"[BSON_DEBUG] Result memory size: {result_mem_size} bytes")
        
        # Check if result contains large objects
        if isinstance(result, dict):
            for key, value in result.items():
                value_size = sys.getsizeof(value)
                if value_size > 100000:  # Log objects larger than 100KB
                    if verbose_debug_mode:
                        logger.debug(f"[BSON_DEBUG] Large object in result: {key} = {value_size} bytes")
                    
                    # Check if this is a BSON Binary object
                    if hasattr(value, '__class__') and 'Binary' in str(type(value)):
                        if verbose_debug_mode:
                            logger.debug(f"[BSON_DEBUG] {key} is BSON Binary object")
                    elif hasattr(value, '__len__'):
                        if verbose_debug_mode:
                            logger.debug(f"[BSON_DEBUG] {key} is array-like with length: {len(value)}")
                        
                        # Sample first few elements to understand data structure
                        if len(value) > 0:
                            sample = value[:5] if len(value) >= 5 else value
                            if verbose_debug_mode:
                                logger.debug(f"[BSON_DEBUG] {key} sample data: {sample}")
    except Exception as e:
        if verbose_debug_mode:
            logger.debug(f"[BSON_DEBUG] Error checking memory: {e}")
    
    memory_check_elapsed = time.time() - memory_check_start
    if verbose_debug_mode:
        logger.debug(f"[BSON_DEBUG] Memory operations check completed in {memory_check_elapsed*1000:.3f}ms")
    
    # Log conversion time for large messages
    elapsed = time.time() - start_time
    if elapsed > 0.01:  # Log if conversion takes more than 10ms
        if verbose_debug_mode:
            logger.debug(f"[BSON_DEBUG] Message conversion for {rostype} took {elapsed*1000:.3f}ms")
    
    # Always log extract_values exit for sensor_msgs
    if rostype and rostype.startswith("sensor_msgs"):
        if verbose_debug_mode:
            logger.debug(f"[BSON_DEBUG] extract_values EXIT: {rostype}, elapsed={elapsed*1000:.3f}ms")
    
    return result


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
    # Optimized version: Avoid expensive str(msg_inst) call for large messages
    # A representation like '_type' member in ROS1 messages is needed: '{package}/{message_name}'.
    # E.g: 'std_msgs/Header'
    
    msg_type = type(msg_inst)
    if msg_type in primitive_types or msg_type in list_types:
        return str(msg_type)
    
    # OPTIMIZATION: Get type info directly from class attributes instead of str(msg_inst)
    # This avoids expensive serialization of large messages (e.g., 3.8MB PointCloud2)
    module_name = msg_type.__module__  # e.g., 'sensor_msgs.msg._point_cloud2'
    class_name = msg_type.__name__     # e.g., 'PointCloud2'
    
    # Parse module name: 'sensor_msgs.msg._point_cloud2' -> 'sensor_msgs'
    parts = module_name.split('.')
    if len(parts) >= 2 and parts[1] == 'msg':
        package = parts[0]  # 'sensor_msgs'
        return f"{package}/{class_name}"
    
    # Fallback for unexpected module structure
    return f"{module_name}/{class_name}"


def msg_class_type_repr(msg_class):
    """Returns a string representation of a ROS2 message type from a class representation."""
    # The string representation of the class is <class '{package}.msg._{message}.{Message}'>
    # (e.g. <class 'std_msgs.msg._string.String'>).
    # This has to be converted to {package}/msg/{Message} (e.g. std_msgs/msg/String).
    class_repr = str(msg_class).split("'")[1].split(".")
    return f"{class_repr[0]}/{class_repr[1]}/{class_repr[3]}"


def _from_inst(inst, rostype, bson_only_mode=False):
    import time
    
    # Special case for uint8[], we encode the string
    for binary_type, expression in ros_binary_types_list_braces:
        match_result = expression.sub(binary_type, rostype)
        
        if match_result in ros_binary_types:
            # Log binary type processing with detailed timing
            if rostype.startswith("uint8"):
                import logging
                binary_start = time.time()
                if verbose_debug_mode:
                    logging.debug(f"[BSON_DEBUG] Processing binary type {rostype} with {len(inst)} elements")
                if verbose_debug_mode:
                    logging.debug(f"[BSON_DEBUG] Binary data type: {type(inst)}")
                
                # Check if this is array.array, list, or other type
                if hasattr(inst, '__class__'):
                    if verbose_debug_mode:
                        logging.debug(f"[BSON_DEBUG] Binary data class: {inst.__class__}")
                    if hasattr(inst, 'tobytes'):
                        if verbose_debug_mode:
                            logging.debug(f"[BSON_DEBUG] Binary data has tobytes() method")
                    if hasattr(inst, '__array_interface__'):
                        if verbose_debug_mode:
                            logging.debug(f"[BSON_DEBUG] Binary data has numpy array interface")
            
            # Use passed parameter instead of global variable for better control
            if bson_only_mode:
                # Zero-copy optimized BSON Binary creation
                if rostype.startswith("uint8"):
                    bson_start = time.time()
                    result = _create_zero_copy_binary(inst)
                    bson_elapsed = time.time() - bson_start
                    if verbose_debug_mode:
                        logging.debug(f"[BSON_DEBUG] BSON Binary creation took {bson_elapsed*1000:.3f}ms")
                    
                    # Log the result characteristics
                    if hasattr(result, '__class__') and 'Binary' in str(type(result)):
                        if verbose_debug_mode:
                            logging.debug(f"[BSON_DEBUG] Created BSON Binary object: {type(result)}")
                    
                    binary_elapsed = time.time() - binary_start
                    if verbose_debug_mode:
                        logging.debug(f"[BSON_DEBUG] Total binary processing took {binary_elapsed*1000:.3f}ms")
                    return result
                else:
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
        # Log list type processing for debugging
        if rostype.startswith("uint8"):
            import logging
            logging.info(f"[ROSBRIDGE LATENCY] Processing as list type {rostype} with {len(inst)} elements")
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
    import time
    start_time = time.time()
    
    # Zero-copy optimization for BSON mode
    if bson_only_mode:
        result = _from_object_inst_zero_copy(inst, rostype)
    else:
        # Standard implementation for JSON mode
        result = _from_object_inst_standard(inst, rostype, bson_only_mode)
    
    elapsed = time.time() - start_time
    if elapsed > 0.01 and rostype.startswith("sensor_msgs"):  # Log for sensor messages taking > 10ms
        import logging
        logging.info(f"[ROSBRIDGE LATENCY] _from_object_inst for {rostype} took {elapsed*1000:.3f}ms")
    
    return result


def _from_object_inst_zero_copy(inst, rostype):
    """Zero-copy optimized message conversion for BSON mode."""
    import time
    start_time = time.time()
    
    # Log entry into zero-copy path
    import logging
    if verbose_debug_mode:
        logging.debug(f"[BSON_DEBUG] Entered _from_object_inst_zero_copy for {rostype}")
    
    # Pre-allocate result dictionary
    fields_start = time.time()
    fields_and_types = inst.get_fields_and_field_types()
    fields_elapsed = time.time() - fields_start
    if verbose_debug_mode:
        logging.debug(f"[BSON_DEBUG] get_fields_and_field_types() took {fields_elapsed*1000:.3f}ms")
    
    msg = {}
    field_count = 0
    
    # Batch field access to minimize getattr() calls
    for field_name, field_rostype in fields_and_types.items():
        field_start = time.time()
        field_count += 1
        
        # Time the getattr operation
        getattr_start = time.time()
        field_inst = getattr(inst, field_name)
        getattr_elapsed = time.time() - getattr_start
        
        if getattr_elapsed > 0.001:  # Log slow getattr operations
            field_size = len(field_inst) if hasattr(field_inst, '__len__') else "unknown"
            if verbose_debug_mode:
                logging.debug(f"[BSON_DEBUG] getattr({field_name}) took {getattr_elapsed*1000:.3f}ms, size: {field_size}")
        
        # Process the field
        process_start = time.time()
        if _is_binary_field(field_rostype):
            if verbose_debug_mode:
                logging.debug(f"[BSON_DEBUG] Processing binary field '{field_name}' with rostype '{field_rostype}'")
            msg[field_name] = _create_zero_copy_binary(field_inst)
        else:
            msg[field_name] = _from_inst(field_inst, field_rostype, bson_only_mode=True)
        process_elapsed = time.time() - process_start
        
        # Log slow field processing - lowered threshold and expanded to all fields
        field_elapsed = time.time() - field_start
        if field_elapsed > 0.001:  # Log any field taking > 1ms
            field_size = len(field_inst) if hasattr(field_inst, '__len__') else "unknown"
            if verbose_debug_mode:
                logging.debug(f"[BSON_DEBUG] Processing field '{field_name}' ({field_size} elements) took {field_elapsed*1000:.3f}ms (getattr: {getattr_elapsed*1000:.3f}ms, process: {process_elapsed*1000:.3f}ms)")
            if field_name == "data":  # Extra details for data field
                if verbose_debug_mode:
                    logging.debug(f"[BSON_DEBUG] Field '{field_name}' rostype: '{field_rostype}', instance type: {type(field_inst)}")
                # Check if this is where the major bottleneck occurs
                if field_elapsed > 0.1:  # More than 100ms
                    if verbose_debug_mode:
                        logging.debug(f"[BSON_DEBUG] MAJOR BOTTLENECK DETECTED in field '{field_name}': {field_elapsed*1000:.3f}ms")
    
    # Log exit from zero-copy path
    total_elapsed = time.time() - start_time
    if verbose_debug_mode:
        logging.debug(f"[BSON_DEBUG] Exited _from_object_inst_zero_copy for {rostype} in {total_elapsed*1000:.3f}ms, processed {field_count} fields")
    
    return msg


def _from_object_inst_standard(inst, rostype, bson_only_mode=False):
    """Standard message conversion implementation."""
    import time
    start_time = time.time()
    
    # Log entry into standard path
    import logging
    logging.info(f"[ROSBRIDGE LATENCY] Entered _from_object_inst_standard for {rostype}")
    
    # Create an empty dict then populate with values from the inst
    msg = {}
    # Equivalent for zip(inst.__slots__, inst._slot_types) in ROS1:
    for field_name, field_rostype in inst.get_fields_and_field_types().items():
        field_inst = getattr(inst, field_name)
        msg[field_name] = _from_inst(field_inst, field_rostype, bson_only_mode)
    
    # Log exit from standard path
    total_elapsed = time.time() - start_time
    logging.info(f"[ROSBRIDGE LATENCY] Exited _from_object_inst_standard for {rostype} in {total_elapsed*1000:.3f}ms")
    
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
    import time
    import logging
    
    start_time = time.time()
    data_size = len(field_inst) if hasattr(field_inst, '__len__') else "unknown"
    if verbose_debug_mode:
        logging.debug(f"[BSON_DEBUG] _create_zero_copy_binary ENTRY: data size {data_size}, type: {type(field_inst)}")
    
    # ROS2 array.array optimization (most common case for PointCloud2)
    if hasattr(field_inst, 'tobytes'):
        # array.array has efficient tobytes() method - zero-copy
        try:
            tobytes_start = time.time()
            byte_data = field_inst.tobytes()
            tobytes_elapsed = time.time() - tobytes_start
            
            bson_start = time.time()
            result = bson.Binary(byte_data)
            bson_elapsed = time.time() - bson_start
            
            total_elapsed = time.time() - start_time
            if verbose_debug_mode:
                logging.debug(f"[BSON_DEBUG] tobytes() path: tobytes={tobytes_elapsed*1000:.3f}ms, BSON.Binary={bson_elapsed*1000:.3f}ms, total={total_elapsed*1000:.3f}ms")
            return result
        except (TypeError, AttributeError) as e:
            if verbose_debug_mode:
                logging.debug(f"[BSON_DEBUG] tobytes() failed: {e}")
            pass
    
    # Direct memory view optimization for NumPy arrays
    if hasattr(field_inst, '__array_interface__'):
        # NumPy array or similar - use memoryview for zero-copy
        try:
            memview_start = time.time()
            memory_view = memoryview(field_inst)
            memview_elapsed = time.time() - memview_start
            
            bson_start = time.time()
            result = bson.Binary(memory_view)
            bson_elapsed = time.time() - bson_start
            
            total_elapsed = time.time() - start_time
            if verbose_debug_mode:
                logging.debug(f"[BSON_DEBUG] numpy memoryview path: memview={memview_elapsed*1000:.3f}ms, BSON.Binary={bson_elapsed*1000:.3f}ms, total={total_elapsed*1000:.3f}ms")
            return result
        except (TypeError, BufferError) as e:
            if verbose_debug_mode:
                logging.debug(f"[BSON_DEBUG] numpy memoryview failed: {e}")
            pass
    
    # Python buffer protocol support
    try:
        # Try to create memoryview directly
        memview_start = time.time()
        memory_view = memoryview(field_inst)
        memview_elapsed = time.time() - memview_start
        
        bson_start = time.time()
        result = bson.Binary(memory_view)
        bson_elapsed = time.time() - bson_start
        
        total_elapsed = time.time() - start_time
        if verbose_debug_mode:
            logging.debug(f"[BSON_DEBUG] direct memoryview path: memview={memview_elapsed*1000:.3f}ms, BSON.Binary={bson_elapsed*1000:.3f}ms, total={total_elapsed*1000:.3f}ms")
        return result
    except (TypeError, ValueError) as e:
        if verbose_debug_mode:
            logging.debug(f"[BSON_DEBUG] direct memoryview failed: {e}")
        pass
    
    # Bytes-like objects optimization
    if isinstance(field_inst, (bytes, bytearray)):
        # Direct bytes - already optimal
        bson_start = time.time()
        result = bson.Binary(field_inst)
        bson_elapsed = time.time() - bson_start
        
        total_elapsed = time.time() - start_time
        if verbose_debug_mode:
            logging.debug(f"[BSON_DEBUG] bytes path: BSON.Binary={bson_elapsed*1000:.3f}ms, total={total_elapsed*1000:.3f}ms")
        return result
    
    # List/tuple of integers (fallback for uint8 arrays)
    if isinstance(field_inst, (list, tuple)) and field_inst:
        sample_check_start = time.time()
        is_byte_array = all(isinstance(x, int) and 0 <= x <= 255 for x in field_inst[:10])  # Sample check
        sample_check_elapsed = time.time() - sample_check_start
        
        if is_byte_array:
            # Convert to bytes efficiently
            try:
                bytes_start = time.time()
                byte_data = bytes(field_inst)
                bytes_elapsed = time.time() - bytes_start
                
                bson_start = time.time()
                result = bson.Binary(byte_data)
                bson_elapsed = time.time() - bson_start
                
                total_elapsed = time.time() - start_time
                if verbose_debug_mode:
                    logging.debug(f"[BSON_DEBUG] list/tuple path: sample_check={sample_check_elapsed*1000:.3f}ms, bytes()={bytes_elapsed*1000:.3f}ms, BSON.Binary={bson_elapsed*1000:.3f}ms, total={total_elapsed*1000:.3f}ms")
                return result
            except (ValueError, TypeError) as e:
                if verbose_debug_mode:
                    logging.debug(f"[BSON_DEBUG] list/tuple bytes() failed: {e}")
                pass
    
    # Fallback to standard BSON Binary creation
    fallback_start = time.time()
    result = bson.Binary(field_inst)
    fallback_elapsed = time.time() - fallback_start
    
    total_elapsed = time.time() - start_time
    if verbose_debug_mode:
        logging.debug(f"[BSON_DEBUG] fallback path: BSON.Binary={fallback_elapsed*1000:.3f}ms, total={total_elapsed*1000:.3f}ms")
    return result


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
