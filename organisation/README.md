# Organisation data

`seats.csv` maps a computer name to where it sits: `computer,odc,floor,seat`. In a virtual desktop (AVD) the name that
matters is the user's own PC (the remote client), when Windows reports it. These rows are **samples**: replace them with
your seat allocation. The ODC rules (subnets, printers, Wi-Fi, VPN) are in `config.yaml` under `organisation`.
