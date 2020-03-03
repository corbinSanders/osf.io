import yaml

with open('osf/features.yaml') as yaml_file:
    yaml_data = yaml.load(yaml_file, Loader=yaml.FullLoader)
    switches = yaml_data['switches']
    flags = yaml_data['flags']
