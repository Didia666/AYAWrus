import threading


class XAIExplanationEngine:
    """
    Explainable AI Engine for Malware Detection System
    Generates human-readable explanations of scan results
    """
    
    # Educational topics for "Learn Why" section
    EDUCATIONAL_TOPICS = {
        "pe_files": {
            "title": "What kind of file is this?",
            "content": """
This is the format Windows uses for programs (.exe files) and shared program files (.dll files).
The file contains instructions and information Windows needs to run it. A file having this format
is normal and does not by itself mean it is dangerous.
            """
        },
        "entropy": {
            "title": "What does file randomness mean?",
            "content": """
The randomness score estimates how predictable the bytes in a file are. A high score can happen when
data is compressed or encrypted, and some malware does that to hide its contents. Many harmless files
are compressed or encrypted too, so this score alone cannot tell whether a file is harmful.
            """
        },
        "imported_apis": {
            "title": "What are the Windows functions a program requests?",
            "content": """
Programs request named Windows functions to do things such as start another program, work with memory,
or access the internet. Some of these requests can be worth reviewing, but legitimate programs use them
too. A listed function is an indicator to investigate, not proof of malware.
            """
        },
        "feature_extraction": {
            "title": "How does the scanner inspect a file?",
            "content": """
The scanner measures characteristics such as file size, byte patterns, sections, and Windows functions
used by the program. It turns these measurements into numbers for the detection model. The details shown
here describe the file; they do not identify exactly which measurements caused the model's decision.
            """
        },
        "random_forest": {
            "title": "How does the detection model decide?",
            "content": """
The detection model combines many small decision rules and uses their combined result to classify a file.
It can make mistakes, so treat a detection as a warning to review the file, not a guarantee.
            """
        },
        "confidence_score": {
            "title": "What does the confidence score mean?",
            "content": """
This percentage is the model's score for its malware prediction. A higher score means the model leaned
more strongly toward that result; it is not a guarantee that the file is malicious. Safe files can still
be flagged by mistake.
            """
        },
        "false_positives": {
            "title": "Could this warning be a mistake?",
            "content": """
A false alarm happens when a harmless file is marked as a threat. No scanner is perfect. Check the file
and its source before taking action; quarantine is safer than deleting a file straight away.
            """
        },
        "quarantine": {
            "title": "Why quarantine a file?",
            "content": """
Quarantine moves a flagged file somewhere it cannot be opened or run normally. This gives you time to
review it and may let you restore it if it turns out to be harmless. Do not run a file while you are
checking it.
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
        self.feature_evidence = []
        self._analysis_lock = threading.RLock()
    
    def analyze_file(self, file_path: str, file_bytes: bytes, features: list, probability: float, result: str):
        """
        Analyze a scanned file and generate a complete explanation
        """
        with self._analysis_lock:
            return self._analyze_file(file_path, file_bytes, features, probability, result)

    def _analyze_file(self, file_path: str, file_bytes: bytes, features: list, probability: float, result: str):
        self.scan_steps = []
        self.suspicious_characteristics = []
        self.feature_evidence = []
        
        # Keep the scan steps understandable without requiring file-format knowledge.
        self._add_scan_step("Checking the file type", "Checking whether this is a Windows program file.")
        
        self._add_scan_step("Looking at how the file is put together", "Checking the file's main parts and layout.")
        
        self._add_scan_step("Checking how jumbled the file data is", "A high randomness score can happen with compressed or hidden data.")
        
        self._add_scan_step("Checking which Windows functions it uses", "Some functions can be worth a closer look, but are also used by legitimate programs.")
        
        self._add_scan_step("Measuring file characteristics", "Collecting details such as size, byte patterns, and program parts.")
        
        self._add_scan_step("Comparing with known patterns", "The detection model compares these measurements with patterns it has learned.")
        
        self._add_scan_step("Preparing the scan result", "Combining the model's result with the file details.")
        
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
        from collections import Counter

        entropy = self._calculate_entropy(file_bytes)
        self.feature_evidence.append({
            "title": "Basic file details",
            "description": (
                f"Size: {len(file_bytes):,} bytes. Data randomness: {entropy:.2f} out of 8.00 "
                f"(higher means the data is less predictable; this alone does not prove harm). "
                f"Windows program marker: {'found' if file_bytes.startswith(b'MZ') else 'not found'}. "
                f"First four bytes (file signature): {file_bytes[:4].hex(' ').upper() or 'none'}."
            ),
        })

        if file_bytes:
            byte_counts = Counter(file_bytes)
            most_common_bytes = ", ".join(
                f"{value:02X} ({count / len(file_bytes):.1%})"
                for value, count in byte_counts.most_common(5)
            )
            self.feature_evidence.append({
                "title": "Most common data values",
                "description": (
                    f"These are the five most repeated values in the file (shown in hexadecimal): "
                    f"{most_common_bytes}. This low-level detail is mainly useful to analysts."
                ),
            })

        if entropy > 7.0:
            self.suspicious_characteristics.append({
                "type": "high_entropy",
                "title": "The file data is unusually jumbled",
                "description": (
                    f"Randomness score: {entropy:.2f} out of 8.00. This can happen when data is "
                    "compressed or encrypted. It is one clue to review, not proof that the file is harmful."
                )
            })
        
        import pefile

        pe = None
        try:
            pe = pefile.PE(data=file_bytes)
            optional_header = pe.OPTIONAL_HEADER
            machine_names = {
                0x014C: "32-bit Windows (x86)",
                0x8664: "64-bit Windows (x64)",
                0x01C0: "32-bit ARM",
                0xAA64: "64-bit ARM",
            }
            subsystem_names = {
                1: "device/driver",
                2: "Windows graphical app",
                3: "Windows command-line app",
                9: "Windows CE app",
                10: "EFI app",
            }
            self.feature_evidence.append({
                "title": "Windows program information",
                "description": (
                    f"Built for: {machine_names.get(pe.FILE_HEADER.Machine, f'unknown type (0x{pe.FILE_HEADER.Machine:04X})')}. "
                    f"Number of parts: {pe.FILE_HEADER.NumberOfSections}. "
                    f"Program type: {subsystem_names.get(optional_header.Subsystem, f'other (code {optional_header.Subsystem})')}. "
                    f"Windows starts running it at location 0x{optional_header.AddressOfEntryPoint:X}."
                ),
            })

            section_details = []
            high_entropy_sections = []
            for section in pe.sections:
                section_entropy = section.get_entropy()
                section_name = section.Name.decode("utf-8", errors="replace").strip("\x00") or "<unnamed>"
                purpose_flags = []
                if section.__dict__.get("IMAGE_SCN_CNT_CODE"):
                    purpose_flags.append("contains program code")
                if section.__dict__.get("IMAGE_SCN_CNT_INITIALIZED_DATA"):
                    purpose_flags.append("contains stored data")
                if section.__dict__.get("IMAGE_SCN_MEM_EXECUTE"):
                    purpose_flags.append("can be run by the processor")
                if section.__dict__.get("IMAGE_SCN_MEM_READ"):
                    purpose_flags.append("can be read")
                if section.__dict__.get("IMAGE_SCN_MEM_WRITE"):
                    purpose_flags.append("can be changed while running")
                section_details.append((
                    section_entropy,
                    f"Part {section_name}: stored size {section.SizeOfRawData:,} bytes; "
                    f"memory size {section.Misc_VirtualSize:,} bytes; "
                    f"randomness {section_entropy:.2f}/8.00; "
                    f"{', '.join(purpose_flags) or 'purpose not identified'}.",
                ))
                if section_entropy > 7.0:
                    high_entropy_sections.append(f"{section_name} ({section_entropy:.2f})")
            if section_details:
                self.feature_evidence.append({
                    "title": "Main parts of the program (most jumbled first)",
                    "description": "; ".join(
                        detail
                        for _, detail in sorted(section_details, reverse=True)[:8]
                    ),
                })
            if high_entropy_sections:
                self.suspicious_characteristics.append({
                    "type": "high_entropy_sections",
                    "title": "One or more program parts look unusually jumbled",
                    "description": (
                        f"Parts with high randomness: {', '.join(high_entropy_sections)}. "
                        "Compressed or encrypted data can look this way too, so this is not proof of malware."
                    )
                })
            
            suspicious_imports = []
            imports_by_dll = []
            import_count = 0
            if hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
                for entry in pe.DIRECTORY_ENTRY_IMPORT:
                    dll_name = entry.dll.decode("utf-8", errors="replace")
                    dll_imports = []
                    for imp in entry.imports:
                        import_count += 1
                        if imp.name:
                            imp_name = imp.name.decode("utf-8", errors="replace")
                        elif imp.ordinal is not None:
                            imp_name = f"ordinal {imp.ordinal}"
                        else:
                            continue
                        dll_imports.append(imp_name)
                        if imp.name:
                            for suspicious_api in self.SUSPICIOUS_APIS:
                                if suspicious_api.lower() in imp_name.lower():
                                    suspicious_imports.append(imp_name)
                                    break
                    imports_by_dll.append((dll_name, dll_imports))
            if imports_by_dll:
                import_summary = [
                    f"{dll} uses: {', '.join(names[:8]) or 'no named functions'}"
                    for dll, names in imports_by_dll[:8]
                ]
                if len(imports_by_dll) > 8:
                    import_summary.append(f"... and {len(imports_by_dll) - 8} more DLLs")
                entry_label = "entry" if import_count == 1 else "entries"
                self.feature_evidence.append({
                    "title": (
                        f"Windows components and functions this program uses "
                        f"({len(imports_by_dll)} "
                        f"{'DLL' if len(imports_by_dll) == 1 else 'DLLs'}, "
                        f"{import_count} {entry_label})"
                    ),
                    "description": (
                        "These are Windows components (DLLs) and named functions the program asks to use. "
                        "The names below are shown as found in the file. Some can have legitimate uses: "
                        + "; ".join(import_summary)
                    ),
                })
            else:
                self.feature_evidence.append({
                    "title": "Windows components and functions this program uses",
                    "description": "No Windows components or functions were listed in the part of the file we checked.",
                })
            if suspicious_imports:
                unique_imports = list(dict.fromkeys(suspicious_imports))[:10]
                self.suspicious_characteristics.append({
                    "type": "suspicious_imports",
                    "title": "Some requested Windows functions deserve a closer look",
                    "description": (
                        f"The file requests: {', '.join(unique_imports)}. These functions can be used "
                        "for powerful actions, but legitimate software may use them too. Their presence "
                        "alone does not prove the file is malicious."
                    )
                })
            
            if suspicious_imports:
                self.feature_evidence.append({
                    "title": "Windows functions to review",
                    "description": ", ".join(unique_imports),
                })
        except pefile.PEFormatError as exc:
            self.feature_evidence.append({
                "title": "Program details could not be read",
                "description": f"We could not read the Windows program layout ({exc}).",
            })
        finally:
            if pe is not None:
                pe.close()
        
        # Check probability/confidence
        confidence = probability * 100
        if result == "MALICIOUS":
            risk_level = self._get_risk_level(probability)
            self.suspicious_characteristics.append({
                "type": "malicious_prediction",
                "title": "The scanner flagged this file",
                "description": (
                    f"The model gave this file a {confidence:.1f}% malware score "
                    f"(risk level: {risk_level}). This is a warning, not a guarantee."
                )
            })
        elif result == "SUSPICIOUS":
            self.suspicious_characteristics.append({
                "type": "suspicious_prediction",
                "title": "This file has something worth checking",
                "description": "The scan found indicators to review. They do not by themselves confirm malware."
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
            explanation_parts.append(
                f"The detection model flagged this file with a {confidence:.1f}% malware score. "
                "This score is not a guarantee, and harmless files can sometimes be flagged."
            )
        elif result == "SUSPICIOUS":
            explanation_parts.append(
                "This file has characteristics worth checking, but the scan has not confirmed that it is malware."
            )
        else:
            explanation_parts.append("The detection model did not flag this file. No scanner can guarantee a file is safe.")
        
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
            "feature_evidence": self.feature_evidence,
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
