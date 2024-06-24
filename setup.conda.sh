# Download Miniconda installer
wget 'https://repo.anaconda.com/miniconda/Miniconda3-py311_23.11.0-2-Linux-x86_64.sh' -O $HOME/miniconda.sh

# Install Miniconda silently
bash $HOME/miniconda.sh -b -p $HOME/miniconda

# Initialize conda for all shells
$HOME/miniconda/bin/conda init --all
