"""Unit tests for MCP tools/list dump profiles."""
import os
import unittest

from execution.tool_dump import (
    IDE_CORE_DUMP_TOOLS,
    build_input_schema,
    filter_dumped_tools,
    get_dump_profile,
    should_dump_tool,
)


class ToolDumpProfileTests(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("MCP_TOOL_DUMP_PROFILE")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("MCP_TOOL_DUMP_PROFILE", None)
        else:
            os.environ["MCP_TOOL_DUMP_PROFILE"] = self._prev

    def test_default_profile_is_ide_core(self):
        os.environ.pop("MCP_TOOL_DUMP_PROFILE", None)
        self.assertEqual(get_dump_profile(), "ide-core")
        self.assertTrue(should_dump_tool("memory_search"))
        self.assertFalse(should_dump_tool("gdrive_list_files"))
        self.assertFalse(should_dump_tool("read_file"))
        self.assertEqual(len(IDE_CORE_DUMP_TOOLS), 22)

    def test_full_profile_dumps_everything(self):
        os.environ["MCP_TOOL_DUMP_PROFILE"] = "full"
        self.assertEqual(get_dump_profile(), "full")
        self.assertTrue(should_dump_tool("gdrive_list_files"))

    def test_filter_dumped_tools(self):
        os.environ["MCP_TOOL_DUMP_PROFILE"] = "ide-core"
        infos = [
            {"name": "memory_search", "description": "a"},
            {"name": "analyze_image", "description": "b"},
            {"name": "query_db", "description": "c"},
        ]
        dumped = filter_dumped_tools(infos)
        self.assertEqual([t["name"] for t in dumped], ["memory_search", "query_db"])

    def test_build_input_schema_strips_ctx(self):
        def sample(ctx, query: str, limit: int = 5):
            return query

        schema = build_input_schema(sample)
        self.assertNotIn("ctx", schema["properties"])
        self.assertIn("query", schema["properties"])
        self.assertEqual(schema["required"], ["query"])


if __name__ == "__main__":
    unittest.main()
