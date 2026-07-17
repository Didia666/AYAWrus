class XAIExplanationEngine:
    """
    Explainable AI Engine for Malware Detection System
    Generates human-readable explanations of scan results
    """
    
    # Educational topics for "Learn Why" section
    EDUCATIONAL_TOPICS = {
        "pe_files": {
            "title": "What are PE Files?",
            "content": """
PE stands for Portable Executable. It's the standard file format for Windows executables (.exe),
DLLs (.dll), and other system files. PE files contain headers, sections (like code, data, resources),
and information about how the file should be loaded into memory. Malware often modifies PE structures
to avoid detection or make analysis harder.
            """
        },
        "entropy": {
            "title": "What is File Entropy?",
            "content": """
Entropy measures how random or disordered data is. Regular files (like text or images) have low entropy.
Encrypted or compressed files have very high entropy (around 7.0-8.0). Malware often uses encryption
or packing to hide its code, which increases entropy and makes detection harder.
            """
        },
        "imported_apis": {
            "title": "What are Imported APIs?",
            "content": """
APIs (Application Programming Interfaces) are functions that programs use to interact with the operating
system. Malware often uses suspicious APIs like CreateRemoteThread (for code injection), VirtualAlloc
(for memory manipulation), or WinExec (for executing commands). Checking imported APIs helps identify
potentially malicious behavior.
            """
        },
        "feature_extraction": {
            "title": "How Feature Extraction Works",
            "content": """
Feature extraction converts a file into numerical values that a machine learning model can understand.
For malware detection, features include things like file size, entropy, imported APIs, section information,
and more. The EMBER dataset is a common source of these features.
            """
        },
        "random_forest": {
            "title": "What is a Random Forest?",
            "content": """
Random Forest is a machine learning algorithm that uses many decision trees working together. Each tree
makes a prediction, and the forest combines these predictions for the final result. Random Forests are
good at detecting malware because they can handle complex patterns in data and are less prone to overfitting.
            """
        },
        "confidence_score": {
            "title": "Understanding Confidence Scores",
            "content": """
The confidence score (0-100%) tells you how sure the model is of its prediction. A score of 95% means the
model is 95% confident the file is malware. However, high confidence doesn't always mean it's actually
malware - there can still be false positives!
            """
        },
        "false_positives": {
            "title": "What are False Positives?",
            "content": """
A false positive is when a safe file is incorrectly labeled as malware. No malware detector is perfect!
That's why it's important to review detections before taking action, and why we recommend quarantine
instead of immediate deletion.
            """
        },
        "quarantine": {
            "title": "Why Quarantine Instead of Delete?",
            "content": """
Quarantine moves suspicious files to a secure, isolated location instead of deleting them immediately.
This is safer because:
1. You can restore files if they were false positives
2. You can analyze quarantined files later
3. You avoid accidental data loss
Always quarantine first, then review!
            """
        }
    }
    
    # List of suspicious API functions
    SUSPICIOUS_APIS = {
        "CreateRemoteThread", "CreateRemoteThreadEx", "VirtualAlloc", "VirtualAllocEx",
        "VirtualProtect", "VirtualProtectEx", "WriteProcessMemory", "ReadProcessMemory",
        "OpenProcess", "TerminateProcess", "WinExec", "ShellExecute", "ShellExecuteEx",
        "CreateProcess", "CreateProcessAsUser", "CreateProcessWithLogonW", "LoadLibrary",
        "LoadLibraryEx", "GetProcAddress", "CreateFile", "CreateFileMapping", "MapViewOfFile",
        "RegOpenKey", "RegOpenKeyEx", "RegSetValue", "RegSetValueEx", "InternetOpen",
        "InternetOpenUrl", "InternetReadFile", "InternetWriteFile"
    }
    
    def __init__(self):
        self.scan_steps = []
        self.suspicious_characteristics = []
    
    def analyze_file(self, file_path: str, file_bytes: bytes, features: list, probability: float, result: str):
        """
        Analyze a scanned file and generate a complete explanation
        """
        self.scan_steps = []
        self.suspicious_characteristics = []
        
        # Step 1: Verify file type
        self._add_scan_step("Verifying file type...", "Checking if file is a valid PE file")
        
        # Step 2: Analyze PE structure
        self._add_scan_step("Analyzing PE structure...", "Extracting PE headers and sections")
        
        # Step 3: Calculate entropy
        self._add_scan_step("Calculating file entropy...", "Measuring randomness in file data")
        
        # Step 4: Inspect imported APIs
        self._add_scan_step("Inspecting imported APIs...", "Checking for suspicious function imports")
        
        # Step 5: Extract features
        self._add_scan_step("Extracting features...", "Converting file to numerical feature vector")
        
        # Step 6: Run Random Forest model
        self._add_scan_step("Running Random Forest model...", "Classifying file using machine learning")
        
        # Step 7: Generate final prediction
        self._add_scan_step("Generating prediction...", "Finalizing scan results")
        
        # Analyze characteristics
        self._analyze_characteristics(file_path, file_bytes, features, probability, result)
        
        return self._generate_explanation_report(file_path, probability, result)
    
    def _add_scan_step(self, title: str, description: str):
        """Add a step to the scan process simulation"""
        self.scan_steps.append({
            "title": title,
            "description": description
        })
    
    def _analyze_characteristics(self, file_path: str, file_bytes: bytes, features: list, probability: float, result: str):
        """Analyze the file's characteristics and identify suspicious elements"""
        # Calculate entropy (simple version)
        entropy = self._calculate_entropy(file_bytes)
        if entropy > 7.0:
            self.suspicious_characteristics.append({
                "type": "high_entropy",
                "title": "High Entropy Detected",
                "description": f"File entropy: {entropy:.2f}. This may indicate encryption or packing commonly used by malware."
            })
        
        # Analyze PE file (if possible)
        try:
            import pefile
            pe = pefile.PE(data=file_bytes)
            
            # Check section entropy
            high_entropy_sections = []
            for section in pe.sections:
                section_entropy = section.get_entropy()
                if section_entropy > 7.0:
                    high_entropy_sections.append(f"{section.Name.decode('utf-8', errors='ignore').strip()} ({section_entropy:.2f})")
            if high_entropy_sections:
                self.suspicious_characteristics.append({
                    "type": "high_entropy_sections",
                    "title": "High Entropy in Sections",
                    "description": f"Suspicious sections with high entropy: {', '.join(high_entropy_sections)}. Packed or encrypted code often has high entropy."
                })
            
            # Check imported APIs
            suspicious_imports = []
            if hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
                for entry in pe.DIRECTORY_ENTRY_IMPORT:
                    for imp in entry.imports:
                        if imp.name:
                            imp_name = imp.name.decode('utf-8', errors='ignore')
                            for suspicious_api in self.SUSPICIOUS_APIS:
                                if suspicious_api.lower() in imp_name.lower():
                                    suspicious_imports.append(imp_name)
                                    break
            if suspicious_imports:
                unique_imports = list(set(suspicious_imports))[:5]
                self.suspicious_characteristics.append({
                    "type": "suspicious_imports",
                    "title": "Suspicious API Imports",
                    "description": f"Detected potentially malicious APIs: {', '.join(unique_imports)}. These functions are commonly used by malware for injection, process manipulation, or network activity."
                })
            
            pe.close()
        except Exception as e:
            pass
        
        # Check probability/confidence
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
    
    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of file data"""
        if not data:
            return 0.0
        
        from collections import Counter
        import math
        byte_counts = Counter(data)
        entropy = 0.0
        length = len(data)
        
        for count in byte_counts.values():
            p = count / length
            entropy -= p * math.log2(p)
        
        return entropy
    
    def _get_risk_level(self, probability: float) -> str:
        """Get risk level based on probability"""
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
    
    def _generate_explanation_report(self, file_path: str, probability: float, result: str) -> dict:
        """Generate the complete explanation report"""
        confidence = probability * 100
        risk_level = self._get_risk_level(probability)
        
        # Build the detailed explanation
        explanation_parts = []
        
        if result == "MALICIOUS":
            explanation_parts.append(f"The Random Forest model identified this file as malicious with {confidence:.1f}% confidence.")
        elif result == "SUSPICIOUS":
            explanation_parts.append("This file contains suspicious characteristics that warrant further investigation.")
        else:
            explanation_parts.append("The model determined this file is likely safe.")
        
        for char in self.suspicious_characteristics:
            explanation_parts.append(char["description"])
        
        if result in ("MALICIOUS", "SUSPICIOUS"):
            explanation_parts.append("Remember: No detection system is perfect. Review carefully before taking action.")
        
        # Generate action recommendations
        recommendations = self._get_action_recommendations(result, probability, risk_level)
        
        return {
            "prediction": "Malicious" if result == "MALICIOUS" else "Suspicious" if result == "SUSPICIOUS" else "Safe",
            "confidence": confidence,
            "risk_level": risk_level,
            "scan_steps": self.scan_steps,
            "suspicious_characteristics": self.suspicious_characteristics,
            "explanation": "\n\n".join(explanation_parts),
            "recommendations": recommendations,
            "educational_topics": self.EDUCATIONAL_TOPICS
        }
    
    def _get_action_recommendations(self, result: str, probability: float, risk_level: str) -> list:
        """Get recommended actions based on scan result"""
        recommendations = []
        
        if result == "MALICIOUS":
            if probability >= 0.90:
                recommendations.append("Quarantine the file immediately")
                recommendations.append("Do not execute the file")
            elif probability >= 0.70:
                recommendations.append("Quarantine the file")
                recommendations.append("Scan with another antivirus tool for confirmation")
            else:
                recommendations.append("Quarantine the file temporarily")
                recommendations.append("Review the file manually")
        elif result == "SUSPICIOUS":
            recommendations.append("Quarantine the file")
            recommendations.append("Review the suspicious indicators")
        else:
            recommendations.append("Keep the file")
            recommendations.append("Regularly update your antivirus definitions")
        
        return recommendations


xai_engine = XAIExplanationEngine()

__all__ = ["XAIExplanationEngine", "xai_engine"]
