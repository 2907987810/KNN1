"""Sphinx extension for collecting the titles in the rst files and validating
if they follow the capitalization convention.  This sends a warning if
it is not followed.

Usage::

   .. contents::

This will be replaced with nothing (or hello world haha)
"""

from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.builders import Builder

# Use spelling builder as an example!!!!!


class HeadingCapitalizationValidator(Builder):

    name = 'capitalizationValidator'

    def init(self):
        self.docnames = []
        self.document_data = []
        print("BRO")
        return

    def write_doc(self, docname, doctree):
        z = 0
        if z == 0:
            self.error("Warning: capitalization not followed")

        for node in doctree.traverse(nodes.Text):
            if (node.tagname == '#subtitle'):
                print(node.astext())

    def finish(self):
        z = 1
        return


def setup(app):
    app.add_builder(HeadingCapitalizationValidator)
    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }


    # return {
    #     'version': '0.1',
    #     'parallel_read_safe': True,
    #     'parallel_write_safe': True,
    # }
