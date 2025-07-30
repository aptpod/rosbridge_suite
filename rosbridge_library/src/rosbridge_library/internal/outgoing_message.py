from rosbridge_library.internal.cbor_conversion import extract_cbor_values
from rosbridge_library.internal.message_conversion import (
    extract_json_values,
    extract_bson_values,
    verbose_debug_mode,
)

try:
    from cbor import dumps as encode_cbor
except ImportError:
    from rosbridge_library.util.cbor import dumps as encode_cbor


class OutgoingMessage:
    """A message wrapper for caching encoding operations."""

    def __init__(self, message):
        self._message = message
        self._json_values = None
        self._cbor_values = None
        self._cbor_msg = None
        self._cbor_raw_msg = None

    @property
    def message(self):
        return self._message

    def get_json_values(self):
        if self._json_values is None:
            self._json_values = extract_json_values(self._message)
        return self._json_values

    def get_cbor_values(self):
        if self._cbor_values is None:
            self._cbor_values = extract_cbor_values(self._message)
        return self._cbor_values

    def get_cbor(self, outgoing_msg):
        if self._cbor_msg is None:
            outgoing_msg["msg"] = self.get_cbor_values()
            self._cbor_msg = encode_cbor(outgoing_msg)

        return self._cbor_msg

    def get_cbor_raw(self, outgoing_msg):
        if self._cbor_raw_msg is None:
            self._cbor_raw_msg = encode_cbor(outgoing_msg)

        return self._cbor_raw_msg

    def get_bson_values(self):
        """Get message values optimized for BSON with binary efficiency."""
        import time
        start_time = time.time()
        
        # Always log get_bson_values entry with ERROR level to ensure visibility
        import logging
        logger = logging.getLogger(__name__)
        msg_type = str(type(self._message))
        msg_size = getattr(self._message, '__sizeof__', lambda: 0)()
        
        # Log entry
        entry_timestamp = time.time()
        if verbose_debug_mode:
            logger.debug(f"[BSON_DEBUG] get_bson_values ENTRY for {msg_type} (size: {msg_size} bytes)")
        
        # Time the message type conversion for bottleneck investigation
        type_check_start = time.time()
        msg_type_check = str(type(self._message))
        type_check_elapsed = time.time() - type_check_start
        if type_check_elapsed > 0.001:  # Log slow type checks
            if verbose_debug_mode:
                logger.debug(f"[BSON_DEBUG] str(type()) operation took {type_check_elapsed*1000:.3f}ms")
        
        # Time the message sizing for bottleneck investigation  
        sizing_start = time.time()
        msg_size_check = getattr(self._message, '__sizeof__', lambda: 0)()
        sizing_elapsed = time.time() - sizing_start
        if sizing_elapsed > 0.001:  # Log slow sizing operations
            if verbose_debug_mode:
                logger.debug(f"[BSON_DEBUG] message sizing operation took {sizing_elapsed*1000:.3f}ms")
        
        # Log before calling extract_bson_values
        extract_start = time.time()
        pre_extract_elapsed = extract_start - entry_timestamp
        if verbose_debug_mode:
            logger.debug(f"[BSON_DEBUG] About to call extract_bson_values() (pre-processing: {pre_extract_elapsed*1000:.3f}ms)")
        
        result = extract_bson_values(self._message)
        
        extract_elapsed = time.time() - extract_start
        if verbose_debug_mode:
            logger.debug(f"[BSON_DEBUG] extract_bson_values() completed in {extract_elapsed*1000:.3f}ms")
        
        # Log result processing time separately
        result_processing_start = time.time()
        
        # Log result characteristics WITHOUT expensive str(result) conversion
        if isinstance(result, dict):
            # OPTIMIZATION: Avoid expensive str(result) conversion for large BSON Binary objects
            # This was causing 80-110ms bottleneck for 3.7MB PointCloud2 data
            # str(result) with BSON Binary objects creates ~12MB strings causing major slowdown
            
            if verbose_debug_mode:
                logger.debug(f"[BSON_DEBUG] Result is dict with {len(result)} keys")
            
            # Calculate approximate size without expensive string conversion
            approx_size = 0
            large_binary_fields = []
            for key, value in result.items():
                if hasattr(value, '__class__') and 'Binary' in str(type(value)):
                    # BSON Binary object - estimate size without conversion
                    binary_size = len(value) if hasattr(value, '__len__') else 0
                    approx_size += binary_size
                    large_binary_fields.append(f"{key}({binary_size}bytes)")
                else:
                    # Small fields - safe to include
                    approx_size += len(str(value)) if not isinstance(value, dict) else 100  # rough estimate
            
            if verbose_debug_mode:
                logger.debug(f"[BSON_DEBUG] Estimated result size: {approx_size} bytes (optimized calculation)")
            if large_binary_fields:
                if verbose_debug_mode:
                    logger.debug(f"[BSON_DEBUG] Large binary fields: {large_binary_fields}")
            
            # Time the binary field detection
            binary_detection_start = time.time()
            binary_fields = []
            for key, value in result.items():
                if hasattr(value, '__class__') and 'Binary' in str(type(value)):
                    binary_fields.append(key)
            binary_detection_elapsed = time.time() - binary_detection_start
            
            if binary_fields:
                if verbose_debug_mode:
                    logger.debug(f"[BSON_DEBUG] Binary fields found: {binary_fields}")
            if binary_detection_elapsed > 0.001:
                if verbose_debug_mode:
                    logger.debug(f"[BSON_DEBUG] Binary field detection took {binary_detection_elapsed*1000:.3f}ms")
        
        result_processing_elapsed = time.time() - result_processing_start
        if result_processing_elapsed > 0.001:
            if verbose_debug_mode:
                logger.debug(f"[BSON_DEBUG] Result processing took {result_processing_elapsed*1000:.3f}ms")
        
        elapsed = time.time() - start_time
        if verbose_debug_mode:
            logger.debug(f"[BSON_DEBUG] get_bson_values EXIT for {msg_type} took {elapsed*1000:.3f}ms")
        
        # Log breakdown of time if significant delay detected
        if elapsed > 0.1:  # More than 100ms
            extract_percentage = (extract_elapsed / elapsed) * 100 if elapsed > 0 else 0
            other_time = elapsed - extract_elapsed
            if verbose_debug_mode:
                logger.debug(f"[BSON_DEBUG] TIME BREAKDOWN: extract={extract_elapsed*1000:.1f}ms ({extract_percentage:.1f}%), other={other_time*1000:.1f}ms ({100-extract_percentage:.1f}%)")
        
        return result
