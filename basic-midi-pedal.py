import time
import board
import digitalio
import usb_midi
import adafruit_midi
import asyncio
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff
from adafruit_midi.control_change import ControlChange
import analogio

# --- Setup MIDI ---
midi = adafruit_midi.MIDI(midi_out=usb_midi.ports[1], out_channel=0)

# --- Configuration: pins and MIDI notes ---
controls = [
    {"button_pin": board.GP16, "led_pin": board.GP12, "note": 60},  # C4
    {"button_pin": board.GP17, "led_pin": board.GP4, "note": 62},  # D4
    {"button_pin": board.GP18, "led_pin": board.GP6, "note": 64},  # E4
    {"button_pin": board.GP20, "led_pin": board.GP8, "note": 65},  # F4
    {"button_pin": board.GP22, "led_pin": board.GP10, "note": 67},  # G4
    # Add more controls here as needed
]

# --- Pots ---
potControls = [
    {"prev_val": 0, "curr_val": 0, "midi_cc": 1, "pot": analogio.AnalogIn(board.GP26)},
    {"prev_val": 0, "curr_val": 0, "midi_cc": 2, "pot": analogio.AnalogIn(board.GP27)},
    {"prev_val": 0, "curr_val": 0, "midi_cc": 3, "pot": analogio.AnalogIn(board.GP28)},
]


async def read_buttons():
    # --- Initialize hardware and state ---
    for ctrl in controls:
        # Setup button
        btn = digitalio.DigitalInOut(ctrl["button_pin"])
        btn.switch_to_input(pull=digitalio.Pull.UP)
        ctrl["button"] = btn

        # Setup LED
        led = digitalio.DigitalInOut(ctrl["led_pin"])
        led.direction = digitalio.Direction.OUTPUT
        led.value = False
        ctrl["led"] = led

        # Debounce state
        ctrl["prev_state"] = True
        ctrl["last_press_time"] = 0

    debounce_delay = 0.1

    while True:
        now = time.monotonic()

        for ctrl in controls:
            current_button_state = ctrl[
                "button"
            ].value  # True = unpressed, False = pressed

            if (
                not current_button_state
                and ctrl["prev_state"]
                and (now - ctrl["last_press_time"]) > debounce_delay
            ):
                ctrl["last_press_time"] = now

                # Toggle LED
                ctrl["led"].value = not ctrl["led"].value

                # Send MIDI note
                midi.send(NoteOn(note=ctrl["note"], velocity=100))
                await asyncio.sleep(0.1)  # Use async sleep
                midi.send(NoteOff(note=ctrl["note"], velocity=0))

            ctrl["prev_state"] = current_button_state

        await asyncio.sleep(0.01)  # Fast polling for buttons


def make_interpolater(left_min, left_max, right_min, right_max):
    # Figure out how 'wide' each range is
    leftSpan = left_max - left_min
    rightSpan = right_max - right_min

    # Compute the scale factor between left and right values
    scaleFactor = float(rightSpan) / float(leftSpan)

    # create interpolation function using pre-calculated scaleFactor
    def interp_fn(value):
        return right_min + (value - left_min) * scaleFactor

    return interp_fn


async def read_pots():
    pot_to_midi_scaler = make_interpolater(0, 65535, 0, 127)
    while True:
        await asyncio.sleep(0.05)
        for pot_control in potControls:
            pot_control["curr_val"] = round(
                pot_to_midi_scaler(pot_control["pot"].value)
            )
            if abs(pot_control["curr_val"] - pot_control["prev_val"]) > 2:
                pot_control["prev_val"] = pot_control["curr_val"]
                potChange = ControlChange(
                    pot_control["midi_cc"], pot_control["curr_val"]
                )
                midi.send(potChange)


async def main():
    button_task = asyncio.create_task(read_buttons())
    pot_task = asyncio.create_task(read_pots())
    await asyncio.gather(button_task, pot_task)


asyncio.run(main())
