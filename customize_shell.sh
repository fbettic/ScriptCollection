#!/bin/bash
set -e

# Instalacion de dependencias (Debian/Ubuntu/Raspberry Pi OS)
# Se agrega fontconfig para poder actualizar la cache de fuentes del sistema
sudo apt update && sudo apt install -y zsh curl git fontconfig

# --- Instalación de Caskaydia Cove Nerd Font ---
echo "Instalando Caskaydia Cove Nerd Font..."
FONT_DIR="$HOME/.local/share/fonts"
mkdir -p "$FONT_DIR"

# Descargar variantes principales si no existen
if [ ! -f "$FONT_DIR/CaskaydiaCoveNerdFont-Regular.ttf" ]; then
    curl -fLo "$FONT_DIR/CaskaydiaCoveNerdFont-Regular.ttf" https://github.com/ryanoasis/nerd-fonts/raw/HEAD/patched-fonts/CascadiaCode/CaskaydiaCoveNerdFont-Regular.ttf
    curl -fLo "$FONT_DIR/CaskaydiaCoveNerdFont-Bold.ttf" https://github.com/ryanoasis/nerd-fonts/raw/HEAD/patched-fonts/CascadiaCode/CaskaydiaCoveNerdFont-Bold.ttf
    curl -fLo "$FONT_DIR/CaskaydiaCoveNerdFont-Italic.ttf" https://github.com/ryanoasis/nerd-fonts/raw/HEAD/patched-fonts/CascadiaCode/CaskaydiaCoveNerdFont-Italic.ttf
    
    echo "Actualizando caché de fuentes del sistema..."
    fc-cache -fv
else
    echo "Las fuentes ya están instaladas."
fi
# -----------------------------------------------

# Instalacion de Oh My Zsh en modo no interactivo
if [ ! -d "$HOME/.oh-my-zsh" ]; then
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended
fi

# Directorio de plugins personalizados
ZSH_CUSTOM=${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}

# Instalacion de zsh-autosuggestions (Prediccion de comandos)
if [ ! -d "${ZSH_CUSTOM}/plugins/zsh-autosuggestions" ]; then
    git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM}/plugins/zsh-autosuggestions
fi

# Instalacion de zsh-syntax-highlighting
if [ ! -d "${ZSH_CUSTOM}/plugins/zsh-syntax-highlighting" ]; then
    git clone https://github.com/zsh-users/zsh-syntax-highlighting.git ${ZSH_CUSTOM}/plugins/zsh-syntax-highlighting
fi

# Instalacion de Starship
curl -sS https://starship.rs/install.sh | sh -s -- -y

# Aplicar preset Gruvbox Rainbow
mkdir -p ~/.config
starship preset gruvbox-rainbow -o ~/.config/starship.toml

# Configuracion de plugins y herramientas en .zshrc
# z: Navegacion rapida entre directorios basada en historial
# zsh-autosuggestions: Sugerencias basadas en historial
# zsh-syntax-highlighting: Feedback visual de comandos
sed -i 's/plugins=(git)/plugins=(git z zsh-autosuggestions zsh-syntax-highlighting)/' ~/.zshrc

# Inicializacion de Starship en el shell
if ! grep -q 'starship init zsh' ~/.zshrc; then
    echo 'eval "$(starship init zsh)"' >> ~/.zshrc
fi

# Configurar Zsh como shell predeterminada
sudo chsh -s $(which zsh) $USER

echo "--------------------------------------------------------"
echo "Instalacion completada con exito."
echo "RECUERDA: Configura tu app de terminal para usar la fuente 'CaskaydiaCove Nerd Font'."
echo "Reinicia la terminal o ejecuta 'zsh' para iniciar."
echo "--------------------------------------------------------"
