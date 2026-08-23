import yaml
with open("config/tiers.yaml") as f:
    config = yaml.safe_load(f)
print(config["tier_1_planner"])
