#!/usr/bin/env bash
# curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
# nvm install 23
# node -v
# npm -v
#export VSCODE_WORKDIR = $PWD
pip install devtools
pip install pydantic
pip install logfire
pip install mypy
pip install "fastapi[standard]"
git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions
git clone https://github.com/zsh-users/zsh-completions ${ZSH_CUSTOM:-${ZSH:-~/.oh-my-zsh}/custom}/plugins/zsh-completions
git clone https://github.com/zsh-users/zsh-history-substring-search ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-history-substring-search
git clone https://github.com/zsh-users/zsh-syntax-highlighting.git ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting
git clone https://github.com/Baalakay/.dotfiles.git ~/.dotfiles
cd ~/.dotfiles
stow --adopt .
git reset --hard
pip install pydantic-ai
pip install 'pydantic-ai[logfire]'
# pip install 'pydantic-ai[examples]'
cd $LOCAL_WORKSPACE_FOLDER
#echo $cd $VSCODE_WORKDIR
zsh
sudo chsh -s $(which zsh) $(whoami)
source ~/.zshrc