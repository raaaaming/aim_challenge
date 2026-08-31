export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        sea:  { 50:'#eef6ff',100:'#d9ecff',200:'#bcdeff',300:'#8ec8ff',400:'#59a8ff',
                500:'#3286fb',600:'#1c66f0',700:'#1751dd',800:'#1943b3',900:'#1a3c8d',950:'#142556' },
        sand: { 50:'#fbf8f1',100:'#f5eddd',200:'#ead9ba' },
      },
      fontFamily: { sans: ['Pretendard','-apple-system','BlinkMacSystemFont','system-ui','sans-serif'] },
      keyframes: {
        floatUp:   { '0%':{opacity:0,transform:'translateY(14px)'}, '100%':{opacity:1,transform:'translateY(0)'} },
        wave:      { '0%,100%':{transform:'translateX(0)'}, '50%':{transform:'translateX(-25%)'} },
        shimmer:   { '0%':{backgroundPosition:'-500px 0'}, '100%':{backgroundPosition:'500px 0'} },
        popIn:     { '0%':{opacity:0,transform:'scale(.94)'}, '100%':{opacity:1,transform:'scale(1)'} },
      },
      animation: {
        floatUp: 'floatUp .45s cubic-bezier(.22,1,.36,1) both',
        wave: 'wave 7s ease-in-out infinite',
        popIn: 'popIn .4s cubic-bezier(.22,1,.36,1) both',
      },
    },
  },
  plugins: [],
}
