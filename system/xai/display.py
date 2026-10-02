from system.xai.engine import XAIExplanationEngine

xai_engine = XAIExplanationEngine()

def display_xai_explanation(xai_report: dict):
    """
    Display the XAI explanation report in a human-readable format
    """
    if not xai_report:
        print("\nXAI explanation not available for this file.")
        return
    
    print("\n" + "="*80)
    print(" "*30 + "SCAN EXPLANATION")
    print("="*80)
    
    print(f"\nScan result: {xai_report['prediction']}")
    print(f"Model score: {xai_report['confidence']:.1f}% (a guide, not a guarantee)")
    print(f"Risk level: {xai_report['risk_level']}")
    
    print("\n" + "-"*80)
    print("What the scan checked:")
    print("-"*80)
    for i, step in enumerate(xai_report['scan_steps'], 1):
        print(f"  {i}. {step['title']}")
        print(f"     {step['description']}")
    
    if xai_report['suspicious_characteristics']:
        print("\n" + "-"*80)
        print("Things worth a closer look:")
        print("-"*80)
        for char in xai_report['suspicious_characteristics']:
            print(f"  * {char['title']}")
            print(f"    {char['description']}")

    if xai_report.get("feature_evidence"):
        print("\n" + "-"*80)
        print("What we found in the file (these clues do not prove it is harmful):")
        print("-"*80)
        for evidence in xai_report["feature_evidence"]:
            print(f"  * {evidence['title']}")
            print(f"    {evidence['description']}")
    
    print("\n" + "-"*80)
    print("In plain language:")
    print("-"*80)
    print(xai_report['explanation'])
    
    print("\n" + "-"*80)
    print("What you can do:")
    print("-"*80)
    for action in xai_report['recommendations']:
        print(f"  -> {action}")
    
    print("\n" + "-"*80)
    print("Learn more:")
    print("-"*80)
    for topic_key, topic in xai_report['educational_topics'].items():
        print(f"\n{topic['title']}")
        print(f"{topic['content']}")
    
    print("\n" + "="*80)
