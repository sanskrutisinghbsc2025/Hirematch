
import argparse
import sys
import time
import unittest


SUITE_MAPPING = {
    "all": [
        "tests.test_config",
        "tests.test_models",
        "tests.test_database",
        "tests.test_file_validation",
        "tests.test_orchestrator",
        "tests.test_document_processing",
        "tests.test_baseline_matching",
        "tests.test_semantic_matching",
        "tests.test_multi_layer_evaluation",
        "tests.test_scoring_and_shortlisting",
        "tests.test_reporting_and_comparison",
        "tests.test_business_analytics",
        "tests.test_model_lab",
        "tests.test_api_endpoints",
        "tests.test_batch_robustness",
        "tests.test_adversarial_robustness",
        "tests.test_scoring_robustness",
        "tests.test_responsible_ai_and_security",
        "tests.test_resume_quality",
        "tests.test_end_to_end_workflows",
        "tests.test_final_acceptance",
    ],
    "fast": [
        "tests.test_config",
        "tests.test_models",
        "tests.test_database",
        "tests.test_file_validation",
        "tests.test_resume_quality",
        "tests.test_api_endpoints",
        "tests.test_scoring_robustness",
        "tests.test_responsible_ai_and_security",
    ],
    "robustness": [
        "tests.test_batch_robustness",
        "tests.test_adversarial_robustness",
        "tests.test_scoring_robustness",
        "tests.test_responsible_ai_and_security",
    ],
    "e2e": [
        "tests.test_end_to_end_workflows",
        "tests.test_final_acceptance",
    ],
    "acceptance": [
        "tests.test_final_acceptance",
    ],
    "unit": [
        "tests.test_config",
        "tests.test_models",
        "tests.test_database",
        "tests.test_file_validation",
        "tests.test_document_processing",
        "tests.test_baseline_matching",
        "tests.test_scoring_robustness",
        "tests.test_responsible_ai_and_security",
        "tests.test_resume_quality",
    ],
    "integration": [
        "tests.test_orchestrator",
        "tests.test_semantic_matching",
        "tests.test_multi_layer_evaluation",
        "tests.test_scoring_and_shortlisting",
        "tests.test_reporting_and_comparison",
        "tests.test_business_analytics",
        "tests.test_model_lab",
        "tests.test_api_endpoints",
    ],
}


def build_suite(modules):
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for mod in modules:
        try:
            loaded = loader.loadTestsFromName(mod)
            suite.addTest(loaded)
        except Exception as e:
            print(f"Error loading module '{mod}': {e}", file=sys.stderr)
    return suite


def main():
    parser = argparse.ArgumentParser(description="HireMatch Automated Quality Gate Runner")
    parser.add_argument(
        "--suite",
        choices=["all", "fast", "robustness", "e2e", "unit", "integration"],
        default="all",
        help="Select which test suite category to execute.",
    )
    parser.add_argument(
        "--verbosity",
        type=int,
        choices=[1, 2],
        default=2,
        help="Test runner output verbosity.",
    )
    args = parser.parse_args()

    selected_modules = SUITE_MAPPING.get(args.suite, SUITE_MAPPING["all"])
    test_suite = build_suite(selected_modules)

    print("=" * 70)
    print(f"[HireMatch] Quality Assurance Test Runner")
    print(f"   Suite Selected: {args.suite.upper()} ({len(selected_modules)} modules)")
    print(f"   Total Test Cases: {test_suite.countTestCases()}")
    print("=" * 70)

    start_time = time.perf_counter()
    runner = unittest.TextTestRunner(verbosity=args.verbosity)
    result = runner.run(test_suite)
    elapsed = time.perf_counter() - start_time

    print("\n" + "=" * 70)
    print(f"[Summary] Test Execution Summary")
    print(f"   Elapsed Time: {elapsed:.2f}s")
    print(f"   Ran:          {result.testsRun}")
    print(f"   Passed:       {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"   Failures:     {len(result.failures)}")
    print(f"   Errors:       {len(result.errors)}")
    print("=" * 70)

    if not result.wasSuccessful():
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
