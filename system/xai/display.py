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
    print(" "*30 + "AI EXPLANATION PANEL")
    print("="*80)
    
    print(f"\nPrediction: {xai_report['prediction']}")
    print(f"Confidence: {xai_report['confidence']:.1f}%")
    print(f"Risk Level: {xai_report['risk_level']}")
    
    print("\n" + "-"*80)
    print("Scan Process Simulation:")
    print("-"*80)
    for i, step in enumerate(xai_report['scan_steps'], 1):
        print(f"  {i}. {step['title']}")
        print(f"     {step['description']}")
    
    if xai_report['suspicious_characteristics']:
        print("\n" + "-"*80)
        print("Detected Suspicious Characteristics:")
        print("-"*80)
        for char in xai_report['suspicious_characteristics']:
            print(f"  * {char['title']}")
            print(f"    {char['description']}")
    
    print("\n" + "-"*80)
    print("Detailed Explanation:")
    print("-"*80)
    print(xai_report['explanation'])
    
    print("\n" + "-"*80)
    print("Recommended Actions:")
    print("-"*80)
    for action in xai_report['recommendations']:
        print(f"  -> {action}")
    
    print("\n" + "-"*80)
    print("Learn Why:")
    print("-"*80)
    for topic_key, topic in xai_report['educational_topics'].items():
        print(f"\n{topic['title']}")
        print(f"{topic['content']}")
    
    print("\n" + "="*80)
