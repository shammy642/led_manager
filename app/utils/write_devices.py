from pathlib import Path

def write_devices(devices, output_path: Path) -> None:
    lines = []
    for device in devices:
        line = "{name},{ip},{mac}".format(
            name=device["name"],
            ip=device["ip_address"],
            mac=device["mac_address"],
        )
        lines.append(line)

    output_path.write_text("\n".join(lines), encoding="utf-8")