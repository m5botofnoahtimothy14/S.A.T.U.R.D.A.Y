import sounddevice as sd
print("sd version:", sd.__version__)
devs = sd.query_devices()
print(f"DEVCOUNT={len(devs)}")
apis = sd.query_hostapis()
for i, a in enumerate(apis):
    print(f"API {i}: {a['name']} devices={a['devices']}")
for i, d in enumerate(devs):
    api = apis[d["hostapi"]]["name"]
    print(f"{i}: name={d['name']!r} | api={api} | in={d['max_input_channels']} out={d['max_output_channels']} sr={d['default_samplerate']}")
print("DEFAULT:", sd.default.device)
