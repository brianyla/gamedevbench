#!/bin/bash
# Script to compare validation outputs: Original Researchers vs Claude Code vs Codex

cd /Users/brianla/Documents/GitHub/gamedevbench

# Clean up old comparison directory and recreate
rm -rf validation_comparison
mkdir -p validation_comparison

# Create summary header
echo "=== Three-Way Validation Comparison ===" > validation_comparison/SUMMARY.md
echo "" >> validation_comparison/SUMMARY.md
echo "Comparing: Original Researchers | Your Claude Code | Your Codex" >> validation_comparison/SUMMARY.md
echo "" >> validation_comparison/SUMMARY.md
echo "| Task | Original | Claude Code | Codex | Notes |" >> validation_comparison/SUMMARY.md
echo "|------|----------|-------------|-------|-------|" >> validation_comparison/SUMMARY.md

for i in {1..10}; do
    task_num=$(printf "task_%04d" $i)
    echo "Processing $task_num..."

    # Get original researchers' output
    if [ -f "tasks/$task_num/-" ]; then
        orig_output=$(cat "tasks/$task_num/-")
    else
        orig_output="No original validation file found"
    fi

    # Get Claude Code result (most recent)
    claude_dir=$(ls -dt tasks/test_result/${task_num}_claude-code_* 2>/dev/null | head -1)
    if [ -n "$claude_dir" ] && [ -f "$claude_dir/-" ]; then
        claude_output=$(cat "$claude_dir/-")
    else
        claude_output="No Claude Code validation output found"
    fi

    # Get Codex result (most recent)
    codex_dir=$(ls -dt tasks/test_result/${task_num}_codex_* 2>/dev/null | head -1)
    if [ -n "$codex_dir" ] && [ -f "$codex_dir/-" ]; then
        codex_output=$(cat "$codex_dir/-")
    else
        codex_output="No Codex validation output found"
    fi

    # Create comparison file
    comparison_file="validation_comparison/${task_num}_comparison.md"
    echo "=== Three-Way Validation Output Comparison for $task_num ===" > "$comparison_file"
    echo "" >> "$comparison_file"

    echo "## Original Researchers' Output" >> "$comparison_file"
    echo "\`\`\`" >> "$comparison_file"
    echo "$orig_output" >> "$comparison_file"
    echo "\`\`\`" >> "$comparison_file"
    echo "" >> "$comparison_file"

    echo "## Your Claude Code Output" >> "$comparison_file"
    echo "\`\`\`" >> "$comparison_file"
    echo "$claude_output" >> "$comparison_file"
    echo "\`\`\`" >> "$comparison_file"
    echo "" >> "$comparison_file"

    echo "## Your Codex Output" >> "$comparison_file"
    echo "\`\`\`" >> "$comparison_file"
    echo "$codex_output" >> "$comparison_file"
    echo "\`\`\`" >> "$comparison_file"
    echo "" >> "$comparison_file"

    # Determine status for each
    if echo "$orig_output" | grep -q "VALIDATION_PASSED"; then
        orig_status="✅ PASS"
    elif echo "$orig_output" | grep -q "VALIDATION_FAILED"; then
        orig_status="❌ FAIL"
    elif echo "$orig_output" | grep -q "Godot Engine"; then
        orig_status="⏱️ TIMEOUT"
    else
        orig_status="❓ N/A"
    fi

    if echo "$claude_output" | grep -q "VALIDATION_PASSED"; then
        claude_status="✅ PASS"
    elif echo "$claude_output" | grep -q "VALIDATION_FAILED"; then
        claude_status="❌ FAIL"
    elif echo "$claude_output" | grep -q "Godot Engine"; then
        claude_status="⏱️ TIMEOUT"
    else
        claude_status="❓ N/A"
    fi

    if echo "$codex_output" | grep -q "VALIDATION_PASSED"; then
        codex_status="✅ PASS"
    elif echo "$codex_output" | grep -q "VALIDATION_FAILED"; then
        codex_status="❌ FAIL"
    elif echo "$codex_output" | grep -q "Godot Engine"; then
        codex_status="⏱️ TIMEOUT"
    else
        codex_status="❓ N/A"
    fi

    # Determine notes
    notes=""
    if [ "$claude_status" = "✅ PASS" ] && [ "$codex_status" = "✅ PASS" ] && [ "$orig_status" != "✅ PASS" ]; then
        notes="Both improved! 🎉"
    elif [ "$claude_status" = "✅ PASS" ] && [ "$orig_status" != "✅ PASS" ]; then
        notes="Claude improved"
    elif [ "$codex_status" = "✅ PASS" ] && [ "$orig_status" != "✅ PASS" ]; then
        notes="Codex improved"
    elif [ "$claude_status" = "✅ PASS" ] && [ "$codex_status" = "✅ PASS" ]; then
        notes="Both pass"
    elif [ "$orig_status" = "$claude_status" ] && [ "$claude_status" = "$codex_status" ]; then
        notes="All same"
    fi

    # Add to summary
    echo "| $task_num | $orig_status | $claude_status | $codex_status | $notes |" >> validation_comparison/SUMMARY.md

    # Add result to comparison file
    echo "## Comparison Summary" >> "$comparison_file"
    echo "- **Original**: $orig_status" >> "$comparison_file"
    echo "- **Claude Code**: $claude_status" >> "$comparison_file"
    echo "- **Codex**: $codex_status" >> "$comparison_file"
    if [ -n "$notes" ]; then
        echo "- **Notes**: $notes" >> "$comparison_file"
    fi
done

echo ""
echo "=========================================="
echo "Three-Way Comparison Complete!"
echo "=========================================="
echo "Location: validation_comparison/"
echo "Files: task_0001_comparison.md through task_0010_comparison.md"
echo "Summary: validation_comparison/SUMMARY.md"
echo ""
cat validation_comparison/SUMMARY.md
