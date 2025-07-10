#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_srvs.srv import SetBool
from example_interfaces.srv import AddTwoInts


class EchoServices(Node):
    """Echo service nodes for integration testing."""

    def __init__(self):
        super().__init__('echo_services')
        
        # Create SetBool echo service
        self.set_bool_service = self.create_service(
            SetBool,
            '/echo_set_bool',
            self.echo_set_bool_callback
        )
        
        # Create AddTwoInts echo service
        self.add_two_ints_service = self.create_service(
            AddTwoInts,
            '/echo_add_two_ints',
            self.echo_add_two_ints_callback
        )
        
        self.get_logger().info('Echo services started')

    def echo_set_bool_callback(self, request, response):
        """Echo SetBool service callback."""
        self.get_logger().info(f'SetBool request: {request.data}')
        response.success = True
        response.message = f'Echo: {request.data}'
        return response

    def echo_add_two_ints_callback(self, request, response):
        """Echo AddTwoInts service callback."""
        self.get_logger().info(f'AddTwoInts request: {request.a} + {request.b}')
        response.sum = request.a + request.b
        return response


def main(args=None):
    rclpy.init(args=args)
    
    echo_services = EchoServices()
    
    try:
        rclpy.spin(echo_services)
    except KeyboardInterrupt:
        pass
    finally:
        echo_services.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()