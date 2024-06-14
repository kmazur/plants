execute pathogen#infect()
syntax on

colorscheme sonokai

set laststatus=2
set number
set incsearch
set hidden
set cursorline
set clipboard=unnamed
filetype plugin indent on

set tabstop=4

set shiftwidth=4

set softtabstop=4

:set nowrap
:com! Bclose :bp | sp | bn | bd
map <C-X> :Bclose<CR>
map <C-S> :w<CR>


if has("gui_running")
	:set guioptions-=T
	:set guioptions-=m
	:set guioptions-=r
	:set guioptions-=L
	:set guifont=Consolas,10
endif

if exists("g:ctrl_user_command")
  unlet g:ctrlp_user_command
endif
set wildignore+=*\\vendor\\*,*\\node_modules\\*,*\\bower\\*,*\\bower_components\\*,*\\tmp\\*,*.swp,*.zip,*.exe,*\\.git\\*,*\\.hg\\*,*\\.svn\\*,*\\lib\\*,*\\target\\*,*\\target-eclipse\\*


set encoding=utf-8
set fileencoding=utf-8

if has("gui_running")
	au GUIEnter * simalt ~x
endif
