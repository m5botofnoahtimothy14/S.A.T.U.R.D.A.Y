#!/usr/bin/env python3
"""
LiveKit Phone Number Setup Script
Run this to purchase a phone number and configure inbound calling for AEGIS.

Usage:
    python scripts/setup_livekit_phone.py --search US 415
    python scripts/setup_livekit_phone.py --buy +1415555xxxx
    python scripts/setup_livekit_phone.py --setup-dispatch
"""

import asyncio
import argparse
import os
import sys
from livekit import api

def load_env():
    from dotenv import load_dotenv
    load_dotenv()

async def search_numbers(country_code: str, area_code: str = None):
    """Search for available phone numbers."""
    lk_api = get_api()
    
    request = api.SearchPhoneNumbersRequest(
        country_code=country_code,
        area_code=area_code,
        limit=20
    )
    
    result = await lk_api.phone_number.search(request)
    
    print(f"\n=== Available {country_code} Numbers ===")
    for num in result.phone_numbers:
        print(f"  {num.phone_number} - ${num.price}/month")
    
    await lk_api.aclose()

async def purchase_number(phone_number: str, dispatch_rule_id: str = None):
    """Purchase a phone number."""
    lk_api = get_api()
    
    request = api.PurchasePhoneNumberRequest(
        phone_number=phone_number,
    )
    
    try:
        result = await lk_api.phone_number.purchase(request)
        print(f"\n✓ Successfully purchased {phone_number}")
        
        if dispatch_rule_id:
            # Associate with dispatch rule
            await lk_api.phone_number.update_phone_number(
                api.UpdatePhoneNumberRequest(
                    phone_number=phone_number,
                    sip_dispatch_rule_id=dispatch_rule_id
                )
            )
            print(f"✓ Associated with dispatch rule {dispatch_rule_id}")
        
    except Exception as e:
        print(f"✗ Failed to purchase: {e}")
    
    await lk_api.aclose()

async def create_dispatch_rule(room_prefix: str = "aegis"):
    """Create a dispatch rule to route inbound calls to rooms."""
    lk_api = get_api()
    
    # Create inbound trunk for LiveKit Phone Numbers
    trunk = await lk_api.sip.create_sip_inbound_trunk(
        api.CreateSIPInboundTrunkRequest(
            trunk=api.SIPInboundTrunkInfo(
                name="AEGIS Phone Number",
                numbers=[],  # Will be assigned to purchased numbers
                krisp_enabled=True,  # Noise cancellation
            )
        )
    )
    print(f"✓ Created inbound trunk: {trunk.sip_trunk_id}")
    
    # Create dispatch rule
    dispatch = await lk_api.sip.create_sip_dispatch_rule(
        api.CreateSIPDispatchRuleRequest(
            trunk_ids=[trunk.sip_trunk_id],
            rule=api.SIPDispatchRule(
                dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                    room_prefix=room_prefix
                )
            )
        )
    )
    print(f"✓ Created dispatch rule: {dispatch.dispatch_rule_id}")
    print(f"\n→ Use this dispatch rule ID when purchasing numbers:")
    print(f"  {dispatch.dispatch_rule_id}")
    
    await lk_api.aclose()
    return dispatch.dispatch_rule_id

async def list_numbers():
    """List purchased phone numbers."""
    lk_api = get_api()
    
    result = await lk_api.phone_number.list_phone_numbers(
        api.ListPhoneNumbersRequest()
    )
    
    print(f"\n=== Your Phone Numbers ===")
    if result.phone_numbers:
        for num in result.phone_numbers:
            print(f"  {num.phone_number} - {num.sip_trunk_id or 'No trunk'} - {num.sip_dispatch_rule_id or 'No dispatch rule'}")
    else:
        print("  No phone numbers purchased yet")
    
    await lk_api.aclose()

def get_api():
    """Initialize LiveKit API client from environment."""
    url = os.getenv("LIVEKIT_URL")
    key = os.getenv("LIVEKIT_API_KEY")
    secret = os.getenv("LIVEKIT_API_SECRET")
    
    if not all([url, key, secret]):
        print("Error: Missing LIVEKIT_URL, LIVEKIT_API_KEY, or LIVEKIT_API_SECRET")
        print("Check your .env file")
        sys.exit(1)
    
    return api.LiveKitAPI(url=url, api_key=key, api_secret=secret)

async def main():
    parser = argparse.ArgumentParser(description="LiveKit Phone Number Setup")
    parser.add_argument("--search", nargs="+", help="Search for numbers: --search US 415")
    parser.add_argument("--buy", help="Buy a number: --buy +14155551234")
    parser.add_argument("--setup-dispatch", action="store_true", help="Create dispatch rule")
    parser.add_argument("--list", action="store_true", help="List purchased numbers")
    parser.add_argument("--dispatch-rule-id", help="Dispatch rule ID to assign to number")
    
    args = parser.parse_args()
    
    load_env()
    
    if args.search:
        country = args.search[0]
        area = args.search[1] if len(args.search) > 1 else None
        await search_numbers(country, area)
    elif args.buy:
        await purchase_number(args.buy, args.dispatch_rule_id)
    elif args.setup_dispatch:
        await create_dispatch_rule()
    elif args.list:
        await list_numbers()
    else:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main())
