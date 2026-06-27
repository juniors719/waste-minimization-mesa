import os

# Arquivos ou pastas que você quer ignorar
IGNORE_LIST = ['.git', '__pycache__', 'node_modules', '.venv', 'env', 'venv', '.png', '.jpg', '.lock']

with open("projeto_completo.txt", "w", encoding="utf-8") as outfile:
    for root, dirs, files in os.walk("."):
        # Filtra pastas ignoradas
        dirs[:] = [d for d in dirs if d not in IGNORE_LIST]
        
        for file in files:
            if any(file.endswith(ext) for ext in IGNORE_LIST) or file == "projeto_completo.txt":
                continue
                
            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8") as infile:
                    outfile.write(f"\n\n{'='*40}\n")
                    outfile.write(f"FILE: {file_path}\n")
                    outfile.write(f"{'='*40}\n\n")
                    outfile.write(infile.read())
            except Exception:
                # Pula arquivos binários ou que deem erro de leitura
                continue
print("Arquivo projeto_completo.txt gerado com sucesso!")