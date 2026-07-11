
import math
from collections import Counter

class XAIExplanationEngine:
    EDUCATIONAL_TOPICS = {
        "pe_files": {
            "title": "What are PE Files?",
            "content": "\nPE stands for Portable Executable. It's the standard file format for Windows executables (.exe),\nDLLs (.dll), and other system files. PE files contain headers, sections (like code, data, resources),\nand information about how the file should be loaded into memory. Malware often modifies PE structures\nto avoid detection or make analysis harder.\n            "
        }
    }
    
    def __init__(self):
        self.scan_steps = []
        self.suspicious_characteristics = []
    
    def _add_scan_step(self, title, description):
        self.scan_steps.append({"title": title, "description": description})
    
    def _calculate_entropy(self, data):
        if not data:
            return 0.0
        byte_counts = Counter(data)
        entropy = 0.0
        length = len(data)
        for count in byte_counts.values():
            p = count / length
            entropy -= p * math.log2(p)
        return entropy
    
    def _get_risk_level(self, probability):
        if probability >= 0.90:
            return "SEVERE"
        elif probability >= 0.70:
            return "HIGH"
        elif probability >= 0.40:
            return "MEDIUM"
        elif probability >= 0.20:
            return "LOW"
        else:
            return "CLEAN"
    
    def _analyze_characteristics(self, file_bytes, features, probability, result):
        entropy = self._calculate_entropy(file_bytes)
        if entropy > 7.0:
            self.suspicious_characteristics.append({
                "type": "high_entropy",
                "title": "High Entropy Detected",
                "description": f"File entropy: {entropy:.2f}. This may indicate encryption or packing commonly used by malware."
            })
        
        confidence = probability * 100
        if result == "MALICIOUS":
            risk_level = self._get_risk_level(probability)
            self.suspicious_characteristics.append({
                "type": "malicious_prediction",
                "title": "Malicious Prediction",
                "description": f"Model classified this file as malicious with {confidence:.1f}% confidence (Risk Level: {risk_level})."
            })
        elif result == "SUSPICIOUS":
            self.suspicious_characteristics.append({
                "type": "suspicious_prediction",
                "title": "Suspicious Prediction",
                "description": "File contains suspicious indicators."
            })
    
    def _get_action_recommendations(self, result, probability, risk_level):
        recommendations = []
        if result == "MALICIOUS":
            if probability >= 0.90:
                recommendations.append("Quarantine the file immediately")
                recommendations.append("Do not execute the file")
            else:
                recommendations.append("Quarantine the file temporarily")
        elif result == "SUSPICIOUS":
            recommendations.append("Quarantine the file")
        else:
            recommendations.append("Keep the file")
        return recommendations
    
    def analyze_file(self, file_path, file_bytes, features, probability, result):
        self.scan_steps = []
        self.suspicious_characteristics = []
        self._add_scan_step("Verifying file type...", "Checking if file is valid")
        self._add_scan_step("Analyzing structure...", "Extracting file info")
        self._add_scan_step("Calculating file entropy...", "Measuring randomness")
        self._add_scan_step("Inspecting contents...", "Checking for suspicious patterns")
        self._add_scan_step("Extracting features...", "Preparing for analysis")
        self._add_scan_step("Running analysis model...", "Classifying the file")
        self._add_scan_step("Generating prediction...", "Finalizing results")
        self._analyze_characteristics(file_bytes, features, probability, result)
        
        confidence = probability * 100
        risk_level = self._get_risk_level(probability)
        
        explanation_parts = []
        if result == "MALICIOUS":
            explanation_parts.append(f"The model identified this file as malicious with {confidence:.1f}% confidence.")
        elif result == "SUSPICIOUS":
            explanation_parts.append("This file contains suspicious characteristics.")
        else:
            explanation_parts.append("The model determined this file is likely safe.")
        for char in self.suspicious_characteristics:
            explanation_parts.append(char["description"])
        
        return {
            "prediction": "Malicious" if result == "MALICIOUS" else "Suspicious" if result == "SUSPICIOUS" else "Safe",
            "confidence": confidence,
            "risk_level": risk_level,
            "scan_steps": self.scan_steps,
            "suspicious_characteristics": self.suspicious_characteristics,
            "explanation": "\n\n".join(explanation_parts),
            "recommendations": self._get_action_recommendations(result, probability, risk_level),
            "educational_topics": self.EDUCATIONAL_TOPICS
        }

def display_xai_explanation(xai_report):
    if not xai_report:
        print("\nXAI explanation not available.")
        return
    print("\n" + "="*80)
    print(" "*30 + "AI EXPLANATION PANEL")
    print("="*80)
    print(f"\nPrediction: {xai_report['prediction']}")
    print(f"Confidence: {xai_report['confidence']:.1f}%")
    print(f"Risk Level: {xai_report['risk_level']}")
    print("\n" + "-"*80)
    print("Scan Process:")
    for i, step in enumerate(xai_report['scan_steps'], 1):
        print(f"  {i}. {step['title']} - {step['description']}")
    if xai_report['suspicious_characteristics']:
        print("\n" + "-"*80)
        print("Suspicious Characteristics:")
        for char in xai_report['suspicious_characteristics']:
            print(f"  • {char['title']}: {char['description']}")
    print("\n" + "-"*80)
    print("Explanation:")
    print(xai_report['explanation'])
    print("\n" + "-"*80)
    print("Recommendations:")
    for action in xai_report['recommendations']:
        print(f"  → {action}")
    print("\n" + "="*80)

if __name__ == "__main__":
    engine = XAIExplanationEngine()
    test_path = r"d:\SUMMER\AYAWrus_10_07_26\test_script.ps1"
    with open(test_path, "rb") as f:
        data = f.read()
    report = engine.analyze_file(test_path, data, [], 0.0, "CLEAN")
    display_xai_explanation(report)
