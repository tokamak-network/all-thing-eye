#!/usr/bin/env python3
"""
Script to update member EOA (Ethereum) addresses in the database.

EOA addresses extracted from Slack conversation in #all-thing-eye channel.
"""

import sys

sys.path.insert(0, "/Users/son-yeongseong/Desktop/dev/all-thing-eye")

from datetime import datetime
from src.core.config import Config
from src.core.mongo_manager import get_mongo_manager

# EOA addresses extracted from Slack conversation
# Format: (member_name_in_db, eoa_address)
EOA_ADDRESSES = [
    # Name matching with members collection in MongoDB
    ("Aamir", "0x7f88539538ae808e45e23ff6c2b897d062616c4e"),
    ("Jaden", "0x9f1474b5b01940af4f6641bdcbcf8af3ca5197ec"),
    ("Jason", "0x3d827286780dBc00ACE4ee416aD8a4C5dAAC972C"),
    ("Harvey", "0x6E1c4a442E9B9ddA59382ee78058650F1723E0F6"),
    ("Monica", "0x248d48e44da385476072c9d65c043113a3839b91"),
    ("Jake", "0xa4cb7fb1abb9d6f7750bddead7b11f7a3ec4ed10"),  # Jake Jang in Slack
    ("Theo", "0xf109a6faa0c8adae8ccb114f4ab55d47e8fd4be6"),
    ("Aryan", "0x97826f4bf96EFa51Ef92184D7555A9Ac4DD7db80"),  # Aryan Soni in Slack
    (
        "Singh",
        "0xf90432b76A23bC7bB50b868dC4257C5F5B401742",
    ),  # Shailendra/Shailu in Slack
    ("Jeff", "0x5c61cb743bfdca46e829e3e6f1d3b56efbb56e20"),
    ("Mehdi", "0x15759359e60a3b9e59ea7a96d10fa48829f83beb"),
    ("Zena", "0x796c1f28c777b8a5851d356ebbc9dec2ee51137f"),
    ("Irene", "0xa615a44c47e39c23c27eca57a3ea6e65748cf07b"),
    ("Suhyeon", "0x0c37eBe80c3096550CC976B2D5Afa4aE95E444B0"),
    ("Nam", "0x3122c65da0e288fb745f07d8c81b10427b28e7ad"),
    ("Praveen", "0x221BbEb67D83071773157AD895E09D1330673d4F"),  # Praveen S in Slack
    ("Manish", "0x6E0733e7960b3dF52cDb8C995F3B1010846b33de"),  # Manish Kumar in Slack
    ("George", "0xB4032ff3335F0E54Fb0291793B35955e5dA30B0C"),
    ("Rangga", "0xce3025524c751715bc4d941dbdf30b1d94342698"),
    ("Luca", "0x99b2227d5a42c58f632d0152636f06fc89155c17"),
    ("Thomas", "0xb7ae0b891f6ebd3dcf12501465a830d59e4d0b79"),
    ("Muhammed", "0x1a39C31277f7fB4A44F9bb22a47a85e4bB68B307"),
    ("Jeongun Baek", "0x00000000E59C101331dAbA409170159a48300000"),
    ("Eugenie", "0x763d8edabee545bf49082b910e3715f3048f21cc"),
    ("Jamie", "0x1673d01585Ba5d998E3E7DC0c90f8baca65291c5"),
]


def update_member_eoa_addresses():
    """Update EOA addresses for members in the database."""
    config = Config()

    # Connect to MongoDB using MongoDBManager
    mongo_config = config.get("mongodb", {})
    mongo_manager = get_mongo_manager(mongo_config)
    mongo_manager.connect_sync()
    db = mongo_manager.db
    members_col = db["members"]

    print("=" * 60)
    print("Updating Member EOA Addresses")
    print("=" * 60)

    updated_count = 0
    not_found = []

    for member_name, eoa_address in EOA_ADDRESSES:
        # Find member by name (case-insensitive)
        member = members_col.find_one(
            {"name": {"$regex": f"^{member_name}$", "$options": "i"}}
        )

        if member:
            # Update EOA address
            result = members_col.update_one(
                {"_id": member["_id"]},
                {
                    "$set": {
                        "eoa_address": eoa_address.lower(),  # Store in lowercase
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            if result.modified_count > 0:
                print(f"✅ Updated {member_name}: {eoa_address}")
                updated_count += 1
            else:
                current_eoa = member.get("eoa_address", "None")
                if current_eoa == eoa_address.lower():
                    print(f"⏭️  {member_name}: Already has this EOA address")
                else:
                    print(f"⚠️  {member_name}: Update failed (current: {current_eoa})")
        else:
            not_found.append(member_name)
            print(f"❌ Member not found: {member_name}")

    print()
    print("=" * 60)
    print(f"Summary:")
    print(f"  - Updated: {updated_count}")
    print(f"  - Not found: {len(not_found)}")
    if not_found:
        print(f"  - Missing members: {', '.join(not_found)}")
    print("=" * 60)

    # Show current state
    print("\n📋 Current Members with EOA Addresses:")
    for doc in members_col.find({"eoa_address": {"$exists": True, "$ne": None}}).sort(
        "name", 1
    ):
        print(f"  {doc['name']}: {doc.get('eoa_address', 'N/A')}")

    mongo_manager.close()


if __name__ == "__main__":
    update_member_eoa_addresses()
