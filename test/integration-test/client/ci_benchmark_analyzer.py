#!/usr/bin/env python3
"""
CI Benchmark Result Analyzer
Analyzes benchmark results and generates comparison reports for CI artifacts
"""

import json
import glob
import os
import statistics
from datetime import datetime
import sys


class CIBenchmarkAnalyzer:
    def __init__(self, results_dir="results"):
        self.results_dir = results_dir
        self.analysis = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "environment": "GitHub Actions",
            "results": {}
        }
        
    def find_benchmark_files(self):
        """Find benchmark result files"""
        json_files = glob.glob(f"{self.results_dir}/benchmark-*.json")
        overhead_files = glob.glob(f"{self.results_dir}/*overhead*.txt")
        profiler_files = glob.glob(f"{self.results_dir}/internal-profiler*.txt")
        
        return {
            "json_files": json_files,
            "overhead_files": overhead_files,
            "profiler_files": profiler_files
        }
        
    def analyze_json_results(self, json_files):
        """Analyze JSON benchmark results if available"""
        if not json_files:
            return {"status": "no_json_results"}
            
        json_results = []
        bson_results = []
        
        for file_path in json_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    
                if 'json' in os.path.basename(file_path).lower():
                    json_results.append(data)
                elif 'bson' in os.path.basename(file_path).lower():
                    bson_results.append(data)
                    
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                
        analysis = {
            "json_files_found": len(json_results),
            "bson_files_found": len(bson_results)
        }
        
        if json_results:
            # Analyze latest JSON result
            latest_json = json_results[-1]
            if "end_to_end_latency_ms" in latest_json:
                analysis["json_performance"] = {
                    "avg_latency_ms": latest_json["end_to_end_latency_ms"]["mean"],
                    "avg_message_size": latest_json["message_size_bytes"]["mean"],
                    "encoding": latest_json["summary"]["encoding_efficiency"]
                }
                
        if bson_results:
            # Analyze latest BSON result
            latest_bson = bson_results[-1]
            if "end_to_end_latency_ms" in latest_bson:
                analysis["bson_performance"] = {
                    "avg_latency_ms": latest_bson["end_to_end_latency_ms"]["mean"],
                    "avg_message_size": latest_bson["message_size_bytes"]["mean"],
                    "encoding": latest_bson["summary"]["primary_encoding"],
                    "efficiency": latest_bson["encoding_analysis"]["efficiency_status"]
                }
                
        # Calculate improvement if both available
        if json_results and bson_results and "json_performance" in analysis and "bson_performance" in analysis:
            json_perf = analysis["json_performance"]
            bson_perf = analysis["bson_performance"]
            
            latency_improvement = ((json_perf["avg_latency_ms"] - bson_perf["avg_latency_ms"]) / 
                                 json_perf["avg_latency_ms"]) * 100
            size_improvement = ((json_perf["avg_message_size"] - bson_perf["avg_message_size"]) / 
                              json_perf["avg_message_size"]) * 100
                              
            analysis["performance_comparison"] = {
                "latency_improvement_percent": round(latency_improvement, 1),
                "size_reduction_percent": round(size_improvement, 1),
                "bson_is_better": latency_improvement > 0 and size_improvement > 0
            }
            
        return analysis
        
    def analyze_profiler_output(self, profiler_files):
        """Analyze internal profiler output"""
        if not profiler_files:
            return {"status": "no_profiler_results"}
            
        analysis = {"files_analyzed": len(profiler_files)}
        
        for file_path in profiler_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                # Extract key metrics from profiler output
                if "CONVERSION TIME ANALYSIS" in content:
                    # Parse conversion times
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if "JSON Conversion:" in line and i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            if "Average:" in next_line:
                                avg_time = next_line.split("Average:")[1].split("ms")[0].strip()
                                analysis["json_conversion_ms"] = float(avg_time)
                        elif "BSON Conversion:" in line and i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            if "Average:" in next_line:
                                avg_time = next_line.split("Average:")[1].split("ms")[0].strip()
                                analysis["bson_conversion_ms"] = float(avg_time)
                                
                if "Data Efficiency Analysis:" in content:
                    lines = content.split('\n')
                    for line in lines:
                        if "BSON efficiency gain:" in line:
                            gain = line.split("BSON efficiency gain:")[1].split("%")[0].strip()
                            analysis["bson_efficiency_gain_percent"] = float(gain)
                            
            except Exception as e:
                print(f"Error analyzing {file_path}: {e}")
                
        return analysis
        
    def generate_summary_report(self):
        """Generate comprehensive summary report"""
        files = self.find_benchmark_files()
        
        self.analysis["file_summary"] = {
            "json_benchmark_files": len(files["json_files"]),
            "overhead_analysis_files": len(files["overhead_files"]),
            "profiler_output_files": len(files["profiler_files"])
        }
        
        # Analyze different types of results
        self.analysis["benchmark_analysis"] = self.analyze_json_results(files["json_files"])
        self.analysis["profiler_analysis"] = self.analyze_profiler_output(files["profiler_files"])
        
        # Generate overall assessment
        self.analysis["overall_assessment"] = self.generate_assessment()
        
        return self.analysis
        
    def generate_assessment(self):
        """Generate overall performance assessment"""
        assessment = {
            "status": "analysis_completed",
            "findings": []
        }
        
        # Check benchmark results
        if "performance_comparison" in self.analysis.get("benchmark_analysis", {}):
            comp = self.analysis["benchmark_analysis"]["performance_comparison"]
            
            if comp["bson_is_better"]:
                assessment["findings"].append(
                    f"✅ BSON mode shows {comp['latency_improvement_percent']}% latency improvement "
                    f"and {comp['size_reduction_percent']}% size reduction"
                )
            else:
                assessment["findings"].append("⚠️ BSON mode performance needs investigation")
                
        # Check profiler results
        if "bson_efficiency_gain_percent" in self.analysis.get("profiler_analysis", {}):
            gain = self.analysis["profiler_analysis"]["bson_efficiency_gain_percent"]
            assessment["findings"].append(f"📊 Internal processing shows {gain}% efficiency gain")
            
        # Check conversion times
        profiler = self.analysis.get("profiler_analysis", {})
        if "json_conversion_ms" in profiler and "bson_conversion_ms" in profiler:
            json_time = profiler["json_conversion_ms"]
            bson_time = profiler["bson_conversion_ms"]
            improvement = ((json_time - bson_time) / json_time) * 100
            assessment["findings"].append(
                f"⚡ BSON conversion is {improvement:.1f}% faster than JSON conversion"
            )
            
        if not assessment["findings"]:
            assessment["findings"].append("ℹ️ Limited data available for comprehensive analysis")
            
        return assessment
        
    def save_results(self):
        """Save analysis results to file"""
        output_file = f"{self.results_dir}/ci-benchmark-analysis.json"
        
        with open(output_file, 'w') as f:
            json.dump(self.analysis, f, indent=2)
            
        print(f"Analysis saved to: {output_file}")
        return output_file
        
    def print_summary(self):
        """Print human-readable summary"""
        print("\n" + "="*60)
        print("CI BENCHMARK ANALYSIS SUMMARY")
        print("="*60)
        
        print(f"\nTimestamp: {self.analysis['timestamp']}")
        
        # File summary
        file_summary = self.analysis["file_summary"]
        print(f"\nFiles Found:")
        print(f"  JSON Benchmark Files: {file_summary['json_benchmark_files']}")
        print(f"  Overhead Analysis Files: {file_summary['overhead_analysis_files']}")
        print(f"  Profiler Output Files: {file_summary['profiler_output_files']}")
        
        # Performance summary
        if "performance_comparison" in self.analysis.get("benchmark_analysis", {}):
            comp = self.analysis["benchmark_analysis"]["performance_comparison"]
            print(f"\nPerformance Comparison:")
            print(f"  Latency Improvement: {comp['latency_improvement_percent']}%")
            print(f"  Size Reduction: {comp['size_reduction_percent']}%")
            print(f"  BSON Better: {comp['bson_is_better']}")
            
        # Overall assessment
        assessment = self.analysis["overall_assessment"]
        print(f"\nFindings:")
        for finding in assessment["findings"]:
            print(f"  {finding}")
            
        print("\n" + "="*60)


def main():
    results_dir = sys.argv[1] if len(sys.argv) > 1 else "results"
    
    analyzer = CIBenchmarkAnalyzer(results_dir)
    analyzer.generate_summary_report()
    analyzer.print_summary()
    analyzer.save_results()


if __name__ == "__main__":
    main()