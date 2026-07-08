import ast

with open("frontend/app.py", encoding="utf-8") as f:
    code = f.read()

tree = ast.parse(code)

class IfFinder(ast.NodeVisitor):
    def visit_If(self, node):
        if node.lineno == 600:
            print(f"If node at line {node.lineno}:")
            print(f"  Test: {ast.unparse(node.test)}")
            
            # Print elif/else branches
            current = node
            while current.orelse:
                if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                    next_node = current.orelse[0]
                    print(f"  Elif node at line {next_node.lineno}:")
                    print(f"    Test: {ast.unparse(next_node.test)}")
                    current = next_node
                else:
                    print(f"  Else block contains {len(current.orelse)} nodes, first starts at line {current.orelse[0].lineno}")
                    for node_in_else in current.orelse:
                        print(f"    Node type: {type(node_in_else).__name__} at line {node_in_else.lineno}")
                        if isinstance(node_in_else, ast.Expr):
                            print(f"      Expr content: {ast.unparse(node_in_else)}")
                    break
        self.generic_visit(node)

IfFinder().visit(tree)
