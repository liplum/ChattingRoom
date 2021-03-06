global using System.Diagnostics.CodeAnalysis;
global using ChattingRoom.Core;
global using ChattingRoom.Core.DB.Models;
global using ChattingRoom.Core.Messages;
global using ChattingRoom.Core.Users;
global using ChattingRoom.Core.Utils;
global using IServiceProvider = ChattingRoom.Core.IServiceProvider;
using System.Collections.Concurrent;
using System.Runtime.Serialization;
using ChattingRoom.Core.Networks;
using ChattingRoom.Core.Services;
using ChattingRoom.Server.DB;
using ChattingRoom.Server.Interfaces;
using ChattingRoom.Server.Messages;
using ChattingRoom.Server.Services;
using static ChattingRoom.Core.IServer;

namespace ChattingRoom.Server;
public partial class Monoserver : IServer {

    private BlockingCollection<Task> ScheduledTask {
        get;
    } = new();
    public IServiceProvider ServiceProvider => _container;

    public void Initialize() {
        _network = new(this);
        _container.RegisterSingleton<ILogger, CmdServerLogger>();
        _container.RegisterSingleton<IResourceManager, ResourceManager>();
        _container.RegisterSingleton<IUserService, UserService>();
        _container.RegisterSingleton<IChatRoomService, ChatRoomService>();
        _container.RegisterSingleton<IDatabase, Database>();

        _container.RegisterInstance<INetwork, Network>(_network);
        _container.RegisterInstance<IServer, Monoserver>(this);

        OnRegisterService?.Invoke(_container);

        _container.Close();

        NetworkService = _container.Resolve<INetwork>();
        Logger = _container.Resolve<ILogger>();
        Logger.StartService();
        Database = _container.Resolve<IDatabase>();
        Database.Connect();
    }
    public void Start() {
        if (NetworkService is null) throw new NetworkServiceException();
        NetworkService.StartService();
        InitChannels();
        InitUserService();
        StartMainThread();
    }


    public void AddScheduledTask([NotNull] Action task) {
        ScheduledTask.Add(new(task));
    }

    private void StartMainThread() {
        MainThread = new(() => {
            foreach (var task in ScheduledTask.GetConsumingEnumerable()) task?.Start();
        });
        MainThread.Start();
    }

    private void InitChannels() {
        InitUserChannel();
    }

    private void InitUserService() {
        if (NetworkService is null) throw new NetworkServiceException();
    }

    private void InitUserChannel() {
        User = NetworkService.New(Names.Channel.User);
        User.RegisterMessage<AuthenticationReqMsg, AuthenticationMsgHandler>();
        User.RegisterMessage<AuthenticationResultMsg>();
        User.RegisterMessage<RegisterRequestMsg, RegisterRequestMsgHandler>();
        User.RegisterMessage<RegisterResultMsg>();
        User.RegisterMessage<JoinRoomRequestMsg, JoinRoomRequestMsgHandler>();
        User.RegisterMessage<JoinRoomResultMsg>();
        User.RegisterMessage<CreateRoomReqMsg, CreateRoomReqMsgHandler>();
        User.RegisterMessage<CreateRoomResultMsg>();
        User.RegisterMessage<JoinedRoomsInfoMsg>();

        Friend = NetworkService.New(Names.Channel.Friend);
        Friend.RegisterMessage<AddFriendReqMsg, AddFriendReqMsgHandler>();
        Friend.RegisterMessage<AddFriendReplyMsg, AddFriendReplyMsgHandler>();
        Friend.RegisterMessage<ReceivedFriendRequestsInfoMsg>();
        Friend.RegisterMessage<SentFriendRequestsResultsMsg>();

        Chatting = NetworkService.New(Names.Channel.Chatting);
        Chatting.RegisterMessage<ChattingMsg, ChattingMsgHandler>();
    }

    public ChatRoom? GetChattingRoomBy(int chattingRoomId) {
        return _chatingRoom.ChatRoomId == chattingRoomId ? _chatingRoom : null;
    }
#nullable disable
    private readonly ChatRoom _chatingRoom = new() { ChatRoomId = 12345 };
    private readonly ServiceContainer _container = new() {
        HotReload = false
    };
    private Network _network;
    private Thread MainThread {
        get;
        set;
    }

    public IDatabase Database {
        get;
        set;
    }

    public event OnRegisterServiceHandler OnRegisterService;

    public INetwork NetworkService {
        get => _network;
        private set => _network = (Network)value;
    }
    public IMessageChannel User {
        get;
        private set;
    }
    public IMessageChannel Chatting {
        get;
        private set;
    }
    public IMessageChannel Friend {
        get;
        private set;
    }

    public ILogger Logger {
        get;
        private set;
    }
#nullable enable
}

[Serializable]
public class NetworkServiceException : Exception {
    public NetworkServiceException() {
    }
    public NetworkServiceException(string message) : base(message) { }
    public NetworkServiceException(string message, Exception inner) : base(message, inner) { }
    protected NetworkServiceException(
        SerializationInfo info,
        StreamingContext context) : base(info, context) {
    }
}