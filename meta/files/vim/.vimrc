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
autocmd VimEnter * :NERDTreeClose
map <C-A> :NERDTreeToggle<CR>

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

map <C-F><C-J> :call JsBeautify()<CR>
map <C-F><C-H> :call HtmlBeautify()<CR>
map <C-F><C-G> :call CSSBeautify()<CR>





let g:EasyMotion_do_mapping = 0

nmap s <Plug>(easymotion-s)


let g:EasyMotion_smartcase = 1

map  / <Plug>(easymotion-sn)
omap / <Plug>(easymotion-tn)




map  n <Plug>(easymotion-next)
map  N <Plug>(easymotion-prev)




let g:airline#extensions#tabline#enabled = 1

set encoding=utf-8
set fileencoding=utf-8




noremap <C-TAB>   :MBEbn<CR>
noremap <C-S-TAB> :MBEbp<CR>
noremap <C-PageDown>   :MBEbn<CR>
noremap <C-PageUp> :MBEbp<CR>




let g:DVB_TrimWS = 1
vmap  <expr>  <LEFT>   DVB_Drag('left')
vmap  <expr>  <RIGHT>  DVB_Drag('right')
vmap  <expr>  <DOWN>   DVB_Drag('down')
vmap  <expr>  <UP>     DVB_Drag('up')
vmap  <expr>  D        DVB_Duplicate()



if has("gui_running")
	au GUIEnter * simalt ~x
endif
