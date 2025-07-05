#!/usr/bin/env python3
import socket
import time
import json
import pygame

# --- Configuration ---
# !!! CRITICAL: Replace with your Raspberry Pi's actual IP address !!!
RPI_HOST = '192.168.1.18'
RPI_PORT = 65432  # This must match the port number in your Raspberry Pi script

# --- Controller Configuration ---
JOYSTICK_DEAD_ZONE = 0.18 # Increase if your joystick drifts when centered
MAX_MOTOR_POWER = 255     # The max power value your robot's logic uses

# --- Controller Axis Mapping (Standard for Xbox 360 Controller) ---
# NOTE: If controls are mixed up, you may need to adjust these values.
# A simple way to check is to add `print(f"Axis: {event.axis}, Value: {event.value:.2f}")`
# inside the `pygame.JOYAXISMOTION` event check to see what your controller outputs.
AXIS_LEFT_STICK_X = 0   # For turning: -1 (left) to +1 (right)
AXIS_RIGHT_STICK_Y = 3  # For speed: -1 (up/forward) to +1 (down/backward). The script inverts this.
AXIS_RIGHT_TRIGGER = 5  # For acceleration: -1 (unpressed) to +1 (fully pressed). The script normalizes this.

current_speed = 0.5  # Initial throttle (range 0.0 to 1.0)
speed_step = 0.1     # Increment for speed change
running = True

def get_keyboard_inputs_from_pygame(keys, current_speed):
    """
    Processes keyboard inputs from pygame and returns a dictionary of motor commands.
    """
    # Movement inputs
    forward = keys[pygame.K_w]
    backward = keys[pygame.K_s]
    left = keys[pygame.K_a]
    right = keys[pygame.K_d]

    # Determine direction
    y_input = 0
    x_input = 0
    if forward: y_input += 1
    if backward: y_input -= 1
    if left: x_input -= 1
    if right: x_input += 1

    # Normalize x and y inputs
    if x_input != 0 and y_input != 0:
        x_input *= 0.7071  # Scale for diagonal movement
        y_input *= 0.7071

    # Calculate motor power (tank-style mixing)
    left_power_raw = y_input - x_input
    right_power_raw = y_input + x_input

    # Normalize power if needed
    max_raw_power = max(abs(left_power_raw), abs(right_power_raw))
    if max_raw_power > 1.0:
        left_power_raw /= max_raw_power
        right_power_raw /= max_raw_power

    # Apply current_speed scaling
    left_final_power = left_power_raw * current_speed * MAX_MOTOR_POWER
    right_final_power = right_power_raw * current_speed * MAX_MOTOR_POWER

    # Create the command dictionary
    commands = {
        "front_left": int(left_final_power),
        "back_left": int(left_final_power),
        "front_right": int(right_final_power),
        "back_right": int(right_final_power),
        "active": True
    }
    return commands

def run_network_client():
    """Main function to run the network client and handle controller events."""
    global running, current_speed
    stop_command = json.dumps({ "active": False, "front_left": 0, "back_left": 0, "front_right": 0, "back_right": 0 })

    pygame.init()
    screen = pygame.display.set_mode((400, 300))
    pygame.display.set_caption("Robot Controller")
    font = pygame.font.SysFont(None, 24)
    clock = pygame.time.Clock()

    button_rect = pygame.Rect(150, 125, 100, 50)
    is_sending = False

    while running:
        client_socket = None
        try:
            print(f"Attempting to connect to Raspberry Pi at {RPI_HOST}:{RPI_PORT}...")
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5.0) # Set a timeout for the connection attempt
            client_socket.connect((RPI_HOST, RPI_PORT))
            print("Connection successful!")
            
            # Connection is active, loop until it breaks
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:  # Left click
                            if button_rect.collidepoint(event.pos):
                                is_sending = not is_sending
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_UP:
                            current_speed = min(1.0, current_speed + speed_step)
                            print(f"Increased speed to {current_speed:.1f}")
                        elif event.key == pygame.K_DOWN:
                            current_speed = max(0.0, current_speed - speed_step)
                            print(f"Decreased speed to {current_speed:.1f}")
                        elif event.key == pygame.K_ESCAPE:
                            print("Escape key pressed. Shutting down...")
                            running = False
                        elif event.key == pygame.K_SPACE:
                            is_sending = False
                            print("Space pressed. Stopping robot and stopping sending.")

                keys = pygame.key.get_pressed()

                if is_sending:
                    commands = get_keyboard_inputs_from_pygame(keys, current_speed)
                    message_to_send = json.dumps(commands)
                else:
                    commands = None
                    message_to_send = stop_command

                client_socket.sendall(message_to_send.encode('utf-8'))

                # Drawing
                screen.fill((30, 30, 30))

                # Draw button
                button_color = (0, 200, 0) if is_sending else (200, 0, 0)
                pygame.draw.rect(screen, button_color, button_rect)
                button_text = font.render("START" if not is_sending else "STOP", True, (255, 255, 255))
                text_rect = button_text.get_rect(center=button_rect.center)
                screen.blit(button_text, text_rect)

                # Draw keys held with highlight
                key_labels = ['W', 'A', 'S', 'D']
                key_positions = [(180, 200), (140, 230), (180, 230), (220, 230)]
                key_states = [keys[pygame.K_w], keys[pygame.K_a], keys[pygame.K_s], keys[pygame.K_d]]

                for label, pos, pressed in zip(key_labels, key_positions, key_states):
                    color = (0, 255, 0) if pressed else (180, 180, 180)
                    key_surf = font.render(label, True, color)
                    screen.blit(key_surf, pos)

                # Display current command being sent
                if commands:
                    command_text = json.dumps(commands, indent=2)
                else:
                    command_text = json.dumps({ "active": False })

                # Render multiline command text
                lines = command_text.split('\n')
                for i, line in enumerate(lines):
                    cmd_surf = font.render(line, True, (255, 255, 255))
                    screen.blit(cmd_surf, (10, 10 + i * 20))

                pygame.display.flip()
                clock.tick(30)  # Limit to 30 FPS

        except (socket.timeout, ConnectionRefusedError, ConnectionResetError, BrokenPipeError) as e:
            print(f"Network error: {e}. Will retry in 5 seconds...")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            running = False # Stop on other critical errors
        finally:
            if client_socket:
                try:
                    # Attempt to send a final stop command before closing the socket
                    client_socket.sendall(stop_command.encode('utf-8'))
                    print("Sent final stop command.")
                except Exception as final_e:
                    print(f"Could not send final stop command: {final_e}")
                client_socket.close()

            if running: # If we are not quitting, wait before retrying connection
                time.sleep(5)

    pygame.quit()
    print("Client application shut down.")

if __name__ == '__main__':
    if RPI_HOST == 'YOUR_RASPBERRY_PI_IP_ADDRESS':
        print("!!! WARNING: You must edit this script to set the RPI_HOST variable !!!")
    else:
        run_network_client()