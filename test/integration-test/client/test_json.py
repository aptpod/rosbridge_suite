#!/usr/bin/env python3

import websocket
import json
import threading
import time
import os
import sys
from datetime import datetime

ROSBRIDGE_URL = os.environ.get('ROSBRIDGE_URL', 'ws://localhost:9090')
RESULTS_DIR = os.environ.get('RESULTS_DIR', '/results')

print('Starting JSON mode test...')
print(f'Connecting to: {ROSBRIDGE_URL}')

class ROSBridgeJSONTest:
    def __init__(self):
        self.results = {
            'mode': 'JSON',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'tests': []
        }
        self.message_count = {'chatter': 0, 'pointcloud': 0}
        self.validation_results = {
            'chatter': {'required': 2, 'validated': 0, 'success': False},
            'pointcloud': {'required': 2, 'validated': 0, 'success': False}
        }
        self.ws = None
        self.test_completed = False

    def validate_chatter_message(self, data):
        """Validate chatter message contains 'Hello World' pattern"""
        return data and isinstance(data, str) and 'Hello World' in data

    def validate_pointcloud_message(self, msg):
        """Validate PointCloud2 has valid structure"""
        return (msg.get('width', 0) > 0 and 
                msg.get('height', 0) >= 1 and 
                msg.get('data') and 
                len(msg.get('data', [])) > 0)

    def check_test_completion(self):
        """Check if validation requirements are met"""
        if (self.validation_results['chatter']['validated'] >= self.validation_results['chatter']['required'] and
            self.validation_results['pointcloud']['validated'] >= self.validation_results['pointcloud']['required']):
            
            all_tests_passed = (self.validation_results['chatter']['success'] and 
                              self.validation_results['pointcloud']['success'])
            
            if all_tests_passed:
                print('✅ All validation tests passed! Closing connection...')
                self.results['overall_status'] = 'PASSED'
            else:
                print('❌ Validation tests failed!')
                self.results['overall_status'] = 'FAILED'
            
            self.test_completed = True
            if self.ws:
                self.ws.close()

    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            msg = json.loads(message)
            
            if msg.get('topic') == '/chatter':
                self.message_count['chatter'] += 1
                is_valid = self.validate_chatter_message(msg['msg']['data'])
                
                print(f"Received chatter message #{self.message_count['chatter']}: {msg['msg']['data']} [{'✓' if is_valid else '✗'}]")
                
                if self.message_count['chatter'] <= self.validation_results['chatter']['required']:
                    self.validation_results['chatter']['validated'] += 1
                    if is_valid:
                        self.validation_results['chatter']['success'] = True
                
                self.results['tests'].append({
                    'test': 'chatter_subscribe',
                    'status': 'success' if is_valid else 'validation_failed',
                    'message': f"Received message: {msg['msg']['data']}",
                    'validation': is_valid
                })
                
                self.check_test_completion()
                
            elif msg.get('topic') == '/pointcloud':
                self.message_count['pointcloud'] += 1
                num_points = msg['msg']['width']
                is_valid = self.validate_pointcloud_message(msg['msg'])
                
                print(f"Received pointcloud message #{self.message_count['pointcloud']}: {num_points} points [{'✓' if is_valid else '✗'}]")
                
                if self.message_count['pointcloud'] <= self.validation_results['pointcloud']['required']:
                    self.validation_results['pointcloud']['validated'] += 1
                    if is_valid:
                        self.validation_results['pointcloud']['success'] = True
                
                self.results['tests'].append({
                    'test': 'pointcloud_subscribe',
                    'status': 'success' if is_valid else 'validation_failed',
                    'message': f"Received pointcloud with {num_points} points",
                    'validation': is_valid
                })
                
                self.check_test_completion()
                
            elif msg.get('op') == 'service_response':
                print('Received service response:', msg)
                self.results['tests'].append({
                    'test': 'service_call',
                    'status': 'success',
                    'service': msg.get('service'),
                    'result': msg.get('result', msg.get('values'))
                })
                
        except json.JSONDecodeError as e:
            print(f'Error parsing JSON message: {e}')
            self.results['tests'].append({
                'test': 'message_parse',
                'status': 'error',
                'error': str(e)
            })
            self.results['overall_status'] = 'FAILED'
            if self.ws:
                self.ws.close()

    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f'WebSocket error: {error}')
        self.results['tests'].append({
            'test': 'connection',
            'status': 'error',
            'error': str(error)
        })

    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        print('Connection closed')
        print(f"Total messages received - Chatter: {self.message_count['chatter']}, PointCloud: {self.message_count['pointcloud']}")
        chatter_status = 'PASS' if self.validation_results['chatter']['success'] else 'FAIL'
        pointcloud_status = 'PASS' if self.validation_results['pointcloud']['success'] else 'FAIL'
        print(f"Validation results - Chatter: {chatter_status}, PointCloud: {pointcloud_status}")
        
        self.results['summary'] = {
            'total_messages': self.message_count,
            'validation_results': self.validation_results,
            'connection': 'closed'
        }
        
        self.save_results()
        
        # Exit with appropriate code
        if self.results.get('overall_status') == 'PASSED':
            print('🎉 JSON mode test PASSED')
            sys.exit(0)
        else:
            print('💥 JSON mode test FAILED')
            sys.exit(1)

    def on_open(self, ws):
        """Handle WebSocket connection open"""
        print('Connected to rosbridge server (JSON mode)')
        
        def send_subscriptions():
            # Test 1: Subscribe to chatter topic
            print('Test 1: Subscribing to /chatter topic...')
            subscribe_chatter = {
                'op': 'subscribe',
                'topic': '/chatter',
                'type': 'std_msgs/msg/String'
            }
            ws.send(json.dumps(subscribe_chatter))
            
            # Test 2: Subscribe to pointcloud topic
            time.sleep(1)
            print('Test 2: Subscribing to /pointcloud topic...')
            subscribe_pointcloud = {
                'op': 'subscribe',
                'topic': '/pointcloud',
                'type': 'sensor_msgs/msg/PointCloud2'
            }
            ws.send(json.dumps(subscribe_pointcloud))
            
            # Test 3: Call echo service
            time.sleep(2)
            print('Test 3: Calling /echo_set_bool service...')
            call_service = {
                'op': 'call_service',
                'service': '/echo_set_bool',
                'type': 'std_srvs/srv/SetBool',
                'args': {'data': True}
            }
            ws.send(json.dumps(call_service))
            
            # Test 4: Call add two ints service
            time.sleep(3)
            print('Test 4: Calling /echo_add_two_ints service...')
            call_service2 = {
                'op': 'call_service',
                'service': '/echo_add_two_ints',
                'type': 'example_interfaces/srv/AddTwoInts',
                'args': {'a': 5, 'b': 3}
            }
            ws.send(json.dumps(call_service2))
            
            # Set timeout for test completion
            time.sleep(15)
            if not self.test_completed and ws.sock and ws.sock.connected:
                print('Test timeout reached, closing connection...')
                if 'overall_status' not in self.results:
                    self.results['overall_status'] = 'TIMEOUT'
                ws.close()
        
        # Run subscriptions in a separate thread
        threading.Thread(target=send_subscriptions, daemon=True).start()

    def save_results(self):
        """Save test results to file"""
        os.makedirs(RESULTS_DIR, exist_ok=True)
        timestamp = int(time.time() * 1000)
        filename = f'{RESULTS_DIR}/test-results-json-{timestamp}.json'
        
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f'Results saved to: {filename}')

    def run_test(self):
        """Run the integration test"""
        self.ws = websocket.WebSocketApp(
            ROSBRIDGE_URL,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        self.ws.run_forever()


if __name__ == '__main__':
    test = ROSBridgeJSONTest()
    test.run_test()