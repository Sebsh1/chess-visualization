import re
import os.path
import json

# This program expects a file containing chess games in the Portable Game Notation (pgn) format 
# It further uses metadata following the scheme from https://database.lichess.org/ but it might also work on other sources

class Node:
    def __init__(self, name:str):
        self.name = name
        self.count = 0
        self.percent = 0
        self.winWhite = 0
        self.winBlack = 0
        self.elo_distribution = {k*200: 0 for k in range(9,18)}
        self._children = []
        self.hidden_when_selected_children = []
        self.moves_before = []

def add_to_elo_dist(node: Node, elo:int):
    for key in sorted(node.elo_distribution.keys()):
        if elo <= key:
            node.elo_distribution[key] = node.elo_distribution[key] + 1 
            break

def get_children_names(node: Node):  
    return [child.name for child in node._children]
    
def update_winrate(node:Node, result:str):
    if result == "1-0":
        node.winWhite += 1
    elif result == "0-1":
        node.winBlack += 1
    
def get_json(obj):
  return json.loads(json.dumps(obj, default=lambda o: getattr(o, '__dict__', str(o))))

def preprocessed_game_generator(dataset_location:str):
    with open(dataset_location) as f:
        for line in f:
            if line.startswith("[WhiteElo"):
                # Some games have missing elo, just skip them
                try:
                    elo = int(int(re.search('\d+', line).group()) + int(re.search('\d+', next(f)).group()) / 2)
                except:
                    pass
            if line.startswith("1."):
                # Some games have evaluation injected in move sequence, just skip them
                if re.search(r"[\(\[].*?[\)\]]", line):
                    pass
                else: 
                    # Remove the numbering of moves
                    line = re.sub(r"[0-9]+\. ", "", line) 
                    yield f"{elo} {line}"

def create_move_tree(data_path:str, depth:int):
    root = Node("Start")
    games_counter = 0
    for game in preprocessed_game_generator(data_path):

        games_counter += 1
        if not games_counter % 100000:
            print(f"Processed a total of {games_counter} games")

        sequence = game.split()
        elo = int(sequence.pop(0))
        result = sequence.pop()

        root.count += 1
        update_winrate(root, result)
        add_to_elo_dist(root, elo)
        current_node = root

        for move in sequence[:depth]:
            if move not in get_children_names(current_node):
                new_node = Node(move)
                new_node.count += 1
                if not current_node.name == "Start":
                    new_node.moves_before = current_node.moves_before + [current_node.name]
                update_winrate(new_node, result)
                add_to_elo_dist(new_node, elo)
                current_node._children.append(new_node)
                current_node = new_node
            else:
                current_node = next(node for node in current_node._children if node.name == move)
                current_node.count += 1
                update_winrate(current_node, result)
                add_to_elo_dist(current_node, elo)

    return root

def secondary_pass_over_tree(node:Node, cutoff:int):
    if node.name == "Start":
        node.percent = 100
    if node._children:
        # Adding percentage
        for child in node._children:
            child.percent = child.count / node.count * 100.0
        # Pruning branches
        node._children[:] = [c for c in node._children if c.percent >= cutoff]  
        # Sorting by play-rate
        node._children.sort(key=lambda c: c.count, reverse=True)
        # Normalize elo distribution
        try:
            factor = 1.0 / sum(node.elo_distribution.values())
        except:
            factor = 1.0 / (sum(node.elo_distribution.values()) + 0.00001)

        for k in node.elo_distribution.keys():
            node.elo_distribution[k] = round(node.elo_distribution[k] * factor, 2)

        for child in node._children:  
            secondary_pass_over_tree(child, cutoff=cutoff)

def main():

    data_path = "E:/Downloads/lichess_db_standard_rated_2014-08.pgn"
    depth = 10
    cutoff = 0.5

    print("Creating tree of move sequences...")
    move_tree = create_move_tree(data_path=data_path, depth=depth)

    print("Cleanup pass over tree...")    
    secondary_pass_over_tree(move_tree, cutoff=cutoff)

    print("Writing to move_tree.txt file...")  
    
    with open("move_tree.js", "w+") as f:
        f.write("var tree = ["+ str(get_json(move_tree)) + "];")
    print("Created move_tree.txt file")

if __name__ == "__main__":
    main()
